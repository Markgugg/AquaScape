using System;
using UnityEngine;
using UnityEngine.Tilemaps;

namespace AquaScape
{
    // keeps the hidden cell tilemaps, the display tilemaps and the collision tilemap in sync
    // it also makes the blurred land mask the water shader uses for shallow water and foam
    [ExecuteAlways]
    public class TerrainPainter : MonoBehaviour
    {
        // the three kinds of terrain
        public enum Layer { Ground, Grass, Glass }

        public static TerrainPainter Instance { get; private set; }

        // hidden tilemaps that store what each cell is
        [Header("logical cells")]
        public Tilemap groundCells;
        public Tilemap grassCells;
        public Tilemap glassCells;
        public TileBase cellMarker;

        // visible tilemaps placed half a cell off from the cells
        [Header("display tilemaps")]
        public Tilemap groundDisplay;
        public Tilemap grassDisplay;
        public Tilemap glassDisplay;
        // 16 tiles each, the index is the corner mask, top left 1, top right 2, bottom left 4, bottom right 8
        public TileBase[] groundTiles = new TileBase[16];
        public TileBase[] grassTiles = new TileBase[16];
        public TileBase[] glassTiles = new TileBase[16];
        // extra full tiles mixed in so big areas dont look repeated
        public TileBase[] groundFullVariants;
        public TileBase[] grassFullVariants;

        // blocks every water cell
        [Header("collision")]
        public Tilemap collision;
        public TileBase solidTile;

        [Header("level size in cells")]
        public RectInt area = new RectInt(0, 0, 120, 32);
        // extra water cells around the edge of the level
        public int border = 3;

        [Header("water mask")]
        // mask pixels for each cell
        public int maskPixelsPerCell = 8;
        // the blurred land mask texture
        public Texture2D LandMask { get; private set; }
        // world area the mask covers as x, y, width, height
        public Vector4 LandMaskRect { get; private set; }
        // called after the mask is rebuilt
        public event Action MaskRebuilt;

        // how tall the cliffs under bottom edges are in cells, same as the art tool
        const float GroundCliff = 40f / 128f;
        const float GlassCliff = 16f / 128f;

        void OnEnable() => Instance = this;

        // helpers to get the right tilemap or tiles for a layer
        Tilemap Cells(Layer l) => l == Layer.Ground ? groundCells : l == Layer.Grass ? grassCells : glassCells;
        Tilemap Display(Layer l) => l == Layer.Ground ? groundDisplay : l == Layer.Grass ? grassDisplay : glassDisplay;
        TileBase[] Tiles(Layer l) => l == Layer.Ground ? groundTiles : l == Layer.Grass ? grassTiles : glassTiles;

        // true if that cell has this layer
        public bool Has(Layer l, Vector3Int c) => Cells(l).HasTile(c);
        public bool Has(Layer l, int x, int y) => Cells(l).HasTile(new Vector3Int(x, y, 0));

        // ground and glass can be walked on
        public bool IsWalkable(Vector3Int c) => Has(Layer.Ground, c) || Has(Layer.Glass, c);

        // world position to cell
        public Vector3Int WorldToCell(Vector2 world) =>
            new Vector3Int(Mathf.FloorToInt(world.x), Mathf.FloorToInt(world.y), 0);

        // middle of a cell in world space
        public static Vector3 CellCenter(Vector3Int c) => new Vector3(c.x + 0.5f, c.y + 0.5f, 0f);

        // what the player is standing on for footstep sounds
        public Surface SurfaceAt(Vector2 world)
        {
            var c = WorldToCell(world);
            if (Has(Layer.Grass, c)) return Surface.Grass;
            if (Has(Layer.Ground, c)) return Surface.Plaza;
            if (Has(Layer.Glass, c)) return Surface.Glass;
            return Surface.Plaza;
        }

        // changes one cell and updates the tiles around it
        public void SetCell(Layer layer, Vector3Int c, bool filled, bool refresh = true)
        {
            Cells(layer).SetTile(c, filled ? cellMarker : null);
            if (!refresh) return;
            // a cell touches the 4 display tiles around it
            for (int dy = -1; dy <= 0; dy++)
                for (int dx = -1; dx <= 0; dx++)
                    RefreshDisplay(layer, new Vector3Int(c.x + dx, c.y + dy, 0));
            RefreshCollision(c);
        }

        // picks the display tile from the 4 cells at its corners
        // each filled corner adds a bit to the mask so there are 16 possible tiles
        void RefreshDisplay(Layer layer, Vector3Int d)
        {
            int mask = (Has(layer, d.x, d.y + 1) ? 1 : 0)        // top left
                     | (Has(layer, d.x + 1, d.y + 1) ? 2 : 0)    // top right
                     | (Has(layer, d.x, d.y) ? 4 : 0)            // bottom left
                     | (Has(layer, d.x + 1, d.y) ? 8 : 0);       // bottom right
            Display(layer).SetTile(d, mask == 0 ? null : PickTile(layer, mask, d));
        }

        // gets the tile for a mask, full tiles sometimes use a variant
        TileBase PickTile(Layer layer, int mask, Vector3Int d)
        {
            var variants = layer == Layer.Ground ? groundFullVariants
                         : layer == Layer.Grass ? grassFullVariants : null;
            if (mask == 15 && variants != null && variants.Length > 0)
            {
                // seed with the cell so it always picks the same one, plain tiles stay most common
                int h = new System.Random(d.x * 1000 + d.y).Next(variants.Length * 10);
                if (h < variants.Length) return variants[h];
            }
            return Tiles(layer)[mask];
        }

        // blocks the cell if its not walkable
        void RefreshCollision(Vector3Int c)
        {
            collision.SetTile(c, IsWalkable(c) ? null : solidTile);
        }

        // rebuilds all display and collision tiles from the cells
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

        // draws the land and cliffs into a small blurred texture
        // 1 is land, about half at the shore, 0 is open water
        public Texture2D BuildLandMask()
        {
            int ppc = maskPixelsPerCell;
            int x0 = area.xMin - border, y0 = area.yMin - border;
            int wCells = area.width + border * 2, hCells = area.height + border * 2;
            int w = wCells * ppc, h = hCells * ppc;
            var data = new float[w * h];

            // a pixel is land if its cell is ground or glass or a cliff hangs down from the cell above
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

            // two box blur passes look like a soft blur, radius is half a cell
            int r = ppc / 2;
            for (int pass = 0; pass < 2; pass++)
            {
                BoxBlur(data, w, h, r, true);
                BoxBlur(data, w, h, r, false);
            }

            // make the texture if its missing or the wrong size
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
            // copy the values into the texture
            var bytes = new byte[w * h];
            for (int i = 0; i < bytes.Length; i++)
                bytes[i] = (byte)Mathf.Clamp(Mathf.RoundToInt(data[i] * 255f), 0, 255);
            LandMask.LoadRawTextureData(bytes);
            LandMask.Apply(false);
            LandMaskRect = new Vector4(x0, y0, wCells, hCells);
            MaskRebuilt?.Invoke();
            return LandMask;
        }

        // blurs one direction using a running sum, edges repeat the last pixel
        static void BoxBlur(float[] d, int w, int h, int r, bool horizontal)
        {
            int len = horizontal ? w : h, lines = horizontal ? h : w;
            var line = new float[len];
            float inv = 1f / (2 * r + 1);
            for (int l = 0; l < lines; l++)
            {
                // copy the row or column out first
                for (int i = 0; i < len; i++)
                    line[i] = d[horizontal ? l * w + i : i * w + l];
                float sum = 0f;
                for (int i = -r; i <= r; i++) sum += line[Mathf.Clamp(i, 0, len - 1)];
                for (int i = 0; i < len; i++)
                {
                    // write the average then slide the window by one
                    d[horizontal ? l * w + i : i * w + l] = sum * inv;
                    sum += line[Mathf.Min(i + r + 1, len - 1)] - line[Mathf.Max(i - r, 0)];
                }
            }
        }
    }
}
