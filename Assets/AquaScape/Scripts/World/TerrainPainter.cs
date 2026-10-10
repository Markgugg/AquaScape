using System;
using UnityEngine;
using UnityEngine.Tilemaps;

namespace AquaScape
{
    /// <summary>
    /// Keeps the level's terrain in sync across three kinds of tilemap:
    ///
    ///  * logical "cell" tilemaps (hidden) that store what each world cell is:
    ///    ground, grass on ground, or glass walkway;
    ///  * "display" tilemaps on a dual grid (offset by half a cell) whose tiles
    ///    are chosen from the 4 cells around each corner, giving rounded,
    ///    seamless island shapes from only 16 tiles per terrain;
    ///  * a collision tilemap that blocks every cell that is open water.
    ///
    /// Gameplay can change terrain at runtime (bridges forming) through SetCell,
    /// and it also produces the blurred land mask the water shader uses for
    /// shallows and shoreline foam.
    /// </summary>
    [ExecuteAlways]
    public class TerrainPainter : MonoBehaviour
    {
        public enum Layer { Ground, Grass, Glass }

        public static TerrainPainter Instance { get; private set; }

        [Header("Logical cells (renderers disabled)")]
        public Tilemap groundCells;
        public Tilemap grassCells;
        public Tilemap glassCells;
        public TileBase cellMarker;

        [Header("Dual-grid display tilemaps")]
        public Tilemap groundDisplay;
        public Tilemap grassDisplay;
        public Tilemap glassDisplay;
        [Tooltip("Index = corner mask (TL=1, TR=2, BL=4, BR=8).")]
        public TileBase[] groundTiles = new TileBase[16];
        public TileBase[] grassTiles = new TileBase[16];
        public TileBase[] glassTiles = new TileBase[16];
        public TileBase[] groundFullVariants;
        public TileBase[] grassFullVariants;

        [Header("Collision")]
        public Tilemap collision;
        public TileBase solidTile;

        [Header("Level extent in cells")]
        public RectInt area = new RectInt(0, 0, 120, 32);
        [Tooltip("Extra water cells drawn/blocked around the level edge.")]
        public int border = 3;

        [Header("Water mask")]
        public int maskPixelsPerCell = 8;
        public Texture2D LandMask { get; private set; }
        /// <summary>World-space rect covered by LandMask (x, y, width, height).</summary>
        public Vector4 LandMaskRect { get; private set; }
        public event Action MaskRebuilt;

        // Height of the cliff faces drawn under south-facing edges, in cells
        // (matches CLIFF_H / GLASS_H in Tools/ArtGen/tiles.py).
        const float GroundCliff = 40f / 128f;
        const float GlassCliff = 16f / 128f;

        void OnEnable() => Instance = this;

        // ------------------------------------------------------------------
        // Queries
        // ------------------------------------------------------------------

        Tilemap Cells(Layer l) => l == Layer.Ground ? groundCells : l == Layer.Grass ? grassCells : glassCells;
        Tilemap Display(Layer l) => l == Layer.Ground ? groundDisplay : l == Layer.Grass ? grassDisplay : glassDisplay;
        TileBase[] Tiles(Layer l) => l == Layer.Ground ? groundTiles : l == Layer.Grass ? grassTiles : glassTiles;

        public bool Has(Layer l, Vector3Int c) => Cells(l).HasTile(c);
        public bool Has(Layer l, int x, int y) => Cells(l).HasTile(new Vector3Int(x, y, 0));

        public bool IsWalkable(Vector3Int c) => Has(Layer.Ground, c) || Has(Layer.Glass, c);

        public Vector3Int WorldToCell(Vector2 world) =>
            new Vector3Int(Mathf.FloorToInt(world.x), Mathf.FloorToInt(world.y), 0);

        public static Vector3 CellCenter(Vector3Int c) => new Vector3(c.x + 0.5f, c.y + 0.5f, 0f);

        /// <summary>What the player is standing on (used for footstep sounds).</summary>
        public Surface SurfaceAt(Vector2 world)
        {
            var c = WorldToCell(world);
            if (Has(Layer.Grass, c)) return Surface.Grass;
            if (Has(Layer.Ground, c)) return Surface.Plaza;
            if (Has(Layer.Glass, c)) return Surface.Glass;
            return Surface.Plaza;
        }

        // ------------------------------------------------------------------
        // Editing
        // ------------------------------------------------------------------

        /// <summary>Change one world cell and refresh the visuals around it.</summary>
        public void SetCell(Layer layer, Vector3Int c, bool filled, bool refresh = true)
        {
            Cells(layer).SetTile(c, filled ? cellMarker : null);
            if (!refresh) return;
            for (int dy = -1; dy <= 0; dy++)
                for (int dx = -1; dx <= 0; dx++)
                    RefreshDisplay(layer, new Vector3Int(c.x + dx, c.y + dy, 0));
            RefreshCollision(c);
        }

        /// <summary>Choose the dual-grid tile for display cell d from its 4 corners.</summary>
        void RefreshDisplay(Layer layer, Vector3Int d)
        {
            int mask = (Has(layer, d.x, d.y + 1) ? 1 : 0)        // top-left
                     | (Has(layer, d.x + 1, d.y + 1) ? 2 : 0)    // top-right
                     | (Has(layer, d.x, d.y) ? 4 : 0)            // bottom-left
                     | (Has(layer, d.x + 1, d.y) ? 8 : 0);       // bottom-right
            Display(layer).SetTile(d, mask == 0 ? null : PickTile(layer, mask, d));
        }

        TileBase PickTile(Layer layer, int mask, Vector3Int d)
        {
            var variants = layer == Layer.Ground ? groundFullVariants
                         : layer == Layer.Grass ? grassFullVariants : null;
            if (mask == 15 && variants != null && variants.Length > 0)
            {
                // deterministic per-cell hash; plain tiles stay the most common
                int h = Mathf.Abs((d.x * 73856093) ^ (d.y * 19349663)) % (variants.Length * 10);
                if (h < variants.Length) return variants[h];
            }
            return Tiles(layer)[mask];
        }

        void RefreshCollision(Vector3Int c)
        {
            collision.SetTile(c, IsWalkable(c) ? null : solidTile);
        }

        /// <summary>Rebuild every display and collision tile from the logical cells.</summary>
        public void RebuildAll()
        {
            groundDisplay.ClearAllTiles();
            grassDisplay.ClearAllTiles();
            glassDisplay.ClearAllTiles();
            collision.ClearAllTiles();
            for (int y = area.yMin - border; y < area.yMax + border; y++)
                for (int x = area.xMin - border; x < area.xMax + border; x++)
                {
                    var d = new Vector3Int(x, y, 0);
                    RefreshDisplay(Layer.Ground, d);
                    RefreshDisplay(Layer.Grass, d);
                    RefreshDisplay(Layer.Glass, d);
                    RefreshCollision(d);
                }
        }

        // ------------------------------------------------------------------
        // Water mask
        // ------------------------------------------------------------------

        /// <summary>
        /// Rasterise land (including cliff faces) into a small blurred texture.
        /// 1 = land, ~0.5 on the shoreline, 0 = open water.
        /// </summary>
        public Texture2D BuildLandMask()
        {
            int ppc = maskPixelsPerCell;
            int x0 = area.xMin - border, y0 = area.yMin - border;
            int wCells = area.width + border * 2, hCells = area.height + border * 2;
            int w = wCells * ppc, h = hCells * ppc;
            var data = new float[w * h];

            for (int py = 0; py < h; py++)
            {
                float wy = y0 + (py + 0.5f) / ppc;
                for (int px = 0; px < w; px++)
                {
                    float wx = x0 + (px + 0.5f) / ppc;
                    int cx = Mathf.FloorToInt(wx);
                    bool land = Has(Layer.Ground, cx, Mathf.FloorToInt(wy))
                             || Has(Layer.Ground, cx, Mathf.FloorToInt(wy + GroundCliff))
                             || Has(Layer.Glass, cx, Mathf.FloorToInt(wy))
                             || Has(Layer.Glass, cx, Mathf.FloorToInt(wy + GlassCliff));
                    data[py * w + px] = land ? 1f : 0f;
                }
            }

            // two box-blur passes ≈ a soft gaussian; radius of half a cell
            int r = ppc / 2;
            for (int pass = 0; pass < 2; pass++)
            {
                BoxBlur(data, w, h, r, true);
                BoxBlur(data, w, h, r, false);
            }

            if (LandMask == null || LandMask.width != w || LandMask.height != h)
            {
                if (LandMask != null) DestroyImmediate(LandMask);
                LandMask = new Texture2D(w, h, TextureFormat.R8, false, true)
                {
                    name = "AquaLandMask",
                    wrapMode = TextureWrapMode.Clamp,
                    filterMode = FilterMode.Bilinear,
                    hideFlags = HideFlags.DontSave
                };
            }
            var bytes = new byte[w * h];
            for (int i = 0; i < bytes.Length; i++)
                bytes[i] = (byte)Mathf.Clamp(Mathf.RoundToInt(data[i] * 255f), 0, 255);
            LandMask.LoadRawTextureData(bytes);
            LandMask.Apply(false);
            LandMaskRect = new Vector4(x0, y0, wCells, hCells);
            MaskRebuilt?.Invoke();
            return LandMask;
        }

        static void BoxBlur(float[] d, int w, int h, int r, bool horizontal)
        {
            int len = horizontal ? w : h, lines = horizontal ? h : w;
            var line = new float[len];
            float inv = 1f / (2 * r + 1);
            for (int l = 0; l < lines; l++)
            {
                for (int i = 0; i < len; i++)
                    line[i] = d[horizontal ? l * w + i : i * w + l];
                float sum = 0f;
                for (int i = -r; i <= r; i++) sum += line[Mathf.Clamp(i, 0, len - 1)];
                for (int i = 0; i < len; i++)
                {
                    d[horizontal ? l * w + i : i * w + l] = sum * inv;
                    sum += line[Mathf.Min(i + r + 1, len - 1)] - line[Mathf.Max(i - r, 0)];
                }
            }
        }
    }
}
