using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.Tilemaps;

namespace AquaScape.EditorTools
{
    /// <summary>
    /// One-click scene builder: AquaScape > Build Level.
    ///
    /// Reads the hand-designed ASCII map (Assets/AquaScape/Level/level.txt),
    /// creates tile assets, prefabs, materials, the player's animator, and then
    /// assembles the whole scene: tilemaps, water, props, gameplay objects,
    /// lighting, post-processing, audio and UI. Rebuilding is deterministic, so
    /// the level can be tweaked in level.py / level.txt and rebuilt any time.
    /// </summary>
    public static partial class AquaScapeBuilder
    {
        const string Root = "Assets/AquaScape/";
        const string Art = Root + "Art/";
        const string ScenePath = Root + "Scenes/AquaScape.unity";
        const string LevelPath = Root + "Level/level.txt";

        static readonly string[] SortingLayers = { "Water", "Underwater", "Ground", "Objects", "FX", "Overhead" };
        const string ObjectChars = "PoCYSBXOGLJMTtferlkAn";

        // map data (y = 0 is the south row)
        static char[,] s_map;
        static int s_w, s_h;

        [MenuItem("AquaScape/Build Level", priority = 0)]
        public static void BuildLevel()
        {
            AquaSpriteImporter.ResetCache();
            AssetDatabase.Refresh();
            EnsureSortingLayers();
            ConfigureRenderer();
            PlayerSettings.productName = "AquaScape";
            PlayerSettings.runInBackground = true;
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            LoadMap();

            var tiles = BuildTileAssets();
            var mats = BuildMaterials();
            var fx = BuildParticlePrefabs(mats);
            var prefabs = BuildPrefabs(mats, fx);
            var animator = BuildPlayerAnimator();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var terrain = BuildTerrain(tiles);
            BuildWater(terrain, mats);
            var cam = BuildCamera();
            var zone = BuildLighting(cam, fx);
            var player = BuildPlayer(animator, mats, fx, prefabs);
            cam.GetComponent<AquaScape.CameraFollow>().target = player.transform;
            zone.nightLights = new[] { player.GetComponentInChildren<Light2D>() };

            PlaceLevelObjects(prefabs, terrain);
            BuildAmbience(fx);
            BuildManagers(prefabs, fx);
            BuildUI();

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log("[AquaScape] Level built: " + ScenePath);
        }

        // =====================================================================
        // Project settings
        // =====================================================================

        static void EnsureSortingLayers()
        {
            var tagManager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = tagManager.FindProperty("m_SortingLayers");
            var existing = new HashSet<string>();
            for (int i = 0; i < layers.arraySize; i++)
                existing.Add(layers.GetArrayElementAtIndex(i).FindPropertyRelative("name").stringValue);

            foreach (var name in SortingLayers)
            {
                if (existing.Contains(name)) continue;
                layers.InsertArrayElementAtIndex(layers.arraySize);
                var e = layers.GetArrayElementAtIndex(layers.arraySize - 1);
                e.FindPropertyRelative("name").stringValue = name;
                e.FindPropertyRelative("uniqueID").intValue = (int)(name.GetHashCode() & 0x7fffffff);
            }
            tagManager.ApplyModifiedProperties();

            // keep our layers in the order listed (after "Default")
            tagManager.Update();
            layers = tagManager.FindProperty("m_SortingLayers");
            for (int target = 0; target < SortingLayers.Length; target++)
            {
                for (int i = 0; i < layers.arraySize; i++)
                {
                    if (layers.GetArrayElementAtIndex(i).FindPropertyRelative("name").stringValue != SortingLayers[target]) continue;
                    layers.MoveArrayElement(i, target + 1);
                    break;
                }
            }
            tagManager.ApplyModifiedProperties();
        }

        /// <summary>Top-down sorting: things lower on screen draw in front.</summary>
        static void ConfigureRenderer()
        {
            var data = AssetDatabase.LoadAssetAtPath<ScriptableObject>("Assets/Settings/Renderer2D.asset");
            var so = new SerializedObject(data);
            so.FindProperty("m_TransparencySortMode").intValue = (int)TransparencySortMode.CustomAxis;
            so.FindProperty("m_TransparencySortAxis").vector3Value = new Vector3(0f, 1f, 0f);
            so.ApplyModifiedProperties();
            EditorUtility.SetDirty(data);
        }

        // =====================================================================
        // Level map
        // =====================================================================

        static void LoadMap()
        {
            var lines = File.ReadAllLines(LevelPath).Where(l => l.Length > 0).ToArray();
            s_h = lines.Length;
            s_w = lines.Max(l => l.Length);
            s_map = new char[s_w, s_h];
            for (int y = 0; y < s_h; y++)
            {
                string row = lines[s_h - 1 - y];
                for (int x = 0; x < s_w; x++)
                    s_map[x, y] = x < row.Length ? row[x] : '.';
            }
        }

        static char At(int x, int y) => x >= 0 && y >= 0 && x < s_w && y < s_h ? s_map[x, y] : '.';

        /// <summary>
        /// Terrain under a cell. Object cells take on the terrain of their
        /// neighbours, so the map can be written with one character per cell.
        /// </summary>
        static char TerrainAt(int x, int y)
        {
            char c = At(x, y);
            if (ObjectChars.IndexOf(c) < 0) return c;
            int g = 0, plaza = 0, glass = 0;
            foreach (var (dx, dy) in new[] { (1, 0), (-1, 0), (0, 1), (0, -1) })
            {
                char n = At(x + dx, y + dy);
                if (n == 'g') g++;
                else if (n == '#') plaza++;
                else if (n == '=' || char.IsDigit(n)) glass++;
            }
            if (g + plaza == 0) return glass > 0 ? '=' : '#';
            // plants always grow out of grass when there is any next to them
            if (g > 0 && "Ttfen".IndexOf(c) >= 0) return 'g';
            return g >= plaza ? 'g' : '#';
        }

        // =====================================================================
        // Tiles + terrain
        // =====================================================================

        class TileSet
        {
            public TileBase[] ground = new TileBase[16], grass = new TileBase[16], glass = new TileBase[16];
            public TileBase[] groundVar, grassVar;
            public TileBase solid, marker;
        }

        static TileSet BuildTileAssets()
        {
            var set = new TileSet();
            for (int m = 1; m < 16; m++)
            {
                set.ground[m] = MakeTile($"ground_{m:00}");
                set.grass[m] = MakeTile($"grass_{m:00}");
                set.glass[m] = MakeTile($"glass_{m:00}");
            }
            set.groundVar = new[] { 1, 2, 3 }.Select(v => MakeTile($"ground_15_v{v}")).ToArray();
            set.grassVar = new[] { 1, 2, 3 }.Select(v => MakeTile($"grass_15_v{v}")).ToArray();
            set.solid = MakeTile("solid", Tile.ColliderType.Grid);
            set.marker = MakeTile("solid", Tile.ColliderType.None, "cell_marker");
            return set;
        }

        static Tile MakeTile(string spriteName, Tile.ColliderType collider = Tile.ColliderType.None, string assetName = null)
        {
            string path = Root + "Tiles/" + (assetName ?? spriteName) + ".asset";
            var tile = AssetDatabase.LoadAssetAtPath<Tile>(path);
            if (tile == null)
            {
                tile = ScriptableObject.CreateInstance<Tile>();
                AssetDatabase.CreateAsset(tile, path);
            }
            tile.sprite = LoadSprite("Tiles/" + spriteName);
            tile.colliderType = collider;
            EditorUtility.SetDirty(tile);
            return tile;
        }

        static AquaScape.TerrainPainter BuildTerrain(TileSet t)
        {
            var gridGo = new GameObject("Terrain", typeof(Grid));
            var painter = gridGo.AddComponent<AquaScape.TerrainPainter>();

            Tilemap Map(string name, string layer, int order, bool visible, Vector3 offset)
            {
                var go = new GameObject(name, typeof(Tilemap), typeof(TilemapRenderer));
                go.transform.SetParent(gridGo.transform, false);
                go.transform.localPosition = offset;
                var r = go.GetComponent<TilemapRenderer>();
                r.sortingLayerName = layer;
                r.sortingOrder = order;
                r.enabled = visible;
                return go.GetComponent<Tilemap>();
            }

            var half = new Vector3(0.5f, 0.5f, 0f);
            painter.groundCells = Map("Cells_Ground", "Ground", 0, false, Vector3.zero);
            painter.grassCells = Map("Cells_Grass", "Ground", 0, false, Vector3.zero);
            painter.glassCells = Map("Cells_Glass", "Ground", 0, false, Vector3.zero);
            painter.glassDisplay = Map("Glass", "Ground", -1, true, half);
            painter.groundDisplay = Map("Ground", "Ground", 0, true, half);
            painter.grassDisplay = Map("Grass", "Ground", 1, true, half);

            painter.collision = Map("Collision", "Ground", 0, false, Vector3.zero);
            var body = painter.collision.gameObject.AddComponent<Rigidbody2D>();
            body.bodyType = RigidbodyType2D.Static;
            var tc = painter.collision.gameObject.AddComponent<TilemapCollider2D>();
            tc.compositeOperation = Collider2D.CompositeOperation.Merge;
            painter.collision.gameObject.AddComponent<CompositeCollider2D>();

            painter.groundTiles = t.ground;
            painter.grassTiles = t.grass;
            painter.glassTiles = t.glass;
            painter.groundFullVariants = t.groundVar;
            painter.grassFullVariants = t.grassVar;
            painter.solidTile = t.solid;
            painter.cellMarker = t.marker;
            painter.area = new RectInt(0, 0, s_w, s_h);
            painter.border = 4;

            for (int y = 0; y < s_h; y++)
                for (int x = 0; x < s_w; x++)
                {
                    char c = TerrainAt(x, y);
                    var cell = new Vector3Int(x, y, 0);
                    if (c == '#' || c == 'g') painter.SetCell(AquaScape.TerrainPainter.Layer.Ground, cell, true, false);
                    if (c == 'g') painter.SetCell(AquaScape.TerrainPainter.Layer.Grass, cell, true, false);
                    if (c == '=') painter.SetCell(AquaScape.TerrainPainter.Layer.Glass, cell, true, false);
                }
            painter.RebuildAll();
            return painter;
        }

        static void BuildWater(AquaScape.TerrainPainter terrain, Materials mats)
        {
            var go = new GameObject("Water", typeof(SpriteRenderer));
            var sr = go.GetComponent<SpriteRenderer>();
            sr.sprite = LoadSprite("Tiles/solid");
            sr.sharedMaterial = mats.water;
            sr.sortingLayerName = "Water";
            const float margin = 24f;
            go.transform.position = new Vector3(s_w * 0.5f, s_h * 0.5f, 0f);
            go.transform.localScale = new Vector3(s_w + margin * 2, s_h + margin * 2, 1f);
            var ws = go.AddComponent<AquaScape.WaterSurface>();
            ws.terrain = terrain;
        }

        // =====================================================================
        // Camera, light, post-processing
        // =====================================================================

        static GameObject BuildCamera()
        {
            var go = new GameObject("Main Camera", typeof(Camera), typeof(AudioListener));
            go.tag = "MainCamera";
            go.transform.position = new Vector3(10, 16, -10);
            var cam = go.GetComponent<Camera>();
            cam.orthographic = true;
            cam.orthographicSize = 5.6f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.1f, 0.6f, 0.8f);
            cam.allowHDR = true;
            var data = go.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            var follow = go.AddComponent<AquaScape.CameraFollow>();
            follow.bounds = new Rect(-3, -2.5f, s_w + 6, s_h + 5);
            follow.titleFrom = new Vector2(8, 17);
            follow.titleTo = new Vector2(24, 15);
            return go;
        }

        static AquaScape.ZoneDirector BuildLighting(GameObject cam, Fx fx)
        {
            var lightGo = new GameObject("Global Light 2D", typeof(Light2D));
            var light = lightGo.GetComponent<Light2D>();
            light.lightType = Light2D.LightType.Global;
            light.intensity = 1f;
            TargetAllLayers(light);

            var zoneGo = new GameObject("Zone Director");
            var zd = zoneGo.AddComponent<AquaScape.ZoneDirector>();
            zd.globalLight = light;
            zd.lagoonToCity = new Vector2(35f, 45f);
            zd.cityToMoon = new Vector2(75f, 86f);
            zd.zones = new[]
            {
                new AquaScape.ZoneDirector.ZoneLook { title = "Blue Lagoon", subtitle = "Bright & peaceful", lightColor = new Color(1f, 0.99f, 0.96f), lightIntensity = 1.0f },
                new AquaScape.ZoneDirector.ZoneLook { title = "Glass City", subtitle = "Futuristic & clean", lightColor = new Color(0.96f, 0.99f, 1.06f), lightIntensity = 1.04f },
                new AquaScape.ZoneDirector.ZoneLook { title = "Moonpool", subtitle = "Dreamy & night", lightColor = new Color(0.46f, 0.47f, 0.98f), lightIntensity = 0.5f },
            };

            // ambient particles that follow the camera
            var amb = new GameObject("Ambient Particles", typeof(AquaScape.FollowCamera));
            zd.dayMotes = Object.Instantiate(fx.dayMotes, amb.transform);
            zd.nightFireflies = Object.Instantiate(fx.fireflies, amb.transform);

            // post-processing
            var volGo = new GameObject("Post Processing", typeof(Volume));
            var vol = volGo.GetComponent<Volume>();
            vol.isGlobal = true;
            vol.sharedProfile = BuildVolumeProfile();
            return zd;
        }

        static VolumeProfile BuildVolumeProfile()
        {
            string path = Root + "Materials/AquaPost.asset";
            var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
            if (profile == null)
            {
                profile = ScriptableObject.CreateInstance<VolumeProfile>();
                AssetDatabase.CreateAsset(profile, path);
            }
            foreach (var c in profile.components.ToArray())
            {
                profile.Remove(c.GetType());
                Object.DestroyImmediate(c, true);
            }
            var bloom = profile.Add<Bloom>(true);
            bloom.threshold.Override(1.0f);
            bloom.intensity.Override(0.6f);
            bloom.scatter.Override(0.72f);
            bloom.tint.Override(new Color(0.85f, 0.97f, 1f));
            var vig = profile.Add<Vignette>(true);
            vig.intensity.Override(0.2f);
            vig.smoothness.Override(0.5f);
            vig.color.Override(new Color(0.02f, 0.12f, 0.3f));
            var ca = profile.Add<ColorAdjustments>(true);
            ca.saturation.Override(10f);
            ca.contrast.Override(6f);
            foreach (var c in profile.components) AssetDatabase.AddObjectToAsset(c, profile);
            EditorUtility.SetDirty(profile);
            return profile;
        }

        public static void TargetAllLayers(Light2D light)
        {
            light.targetSortingLayers = UnityEngine.SortingLayer.layers.Select(l => l.id).ToArray();
        }

        // =====================================================================
        // Managers, audio, UI
        // =====================================================================

        static void BuildManagers(Prefabs prefabs, Fx fx)
        {
            var root = new GameObject("Game");
            root.AddComponent<AquaScape.GameManager>();

            var assets = root.AddComponent<AquaScape.GameAssets>();
            assets.bubblePrefab = prefabs.bubble.GetComponent<AquaScape.Bubble>();
            assets.popFx = fx.pop;
            assets.sparkleFx = fx.sparkle;
            assets.tileFx = fx.tile;
            assets.poofFx = fx.poof;

            var audio = new GameObject("Audio");
            audio.transform.SetParent(root.transform);
            var am = audio.AddComponent<AquaScape.AudioManager>();
            am.footstepPlaza = Clips("footstep_plaza_", 4);
            am.footstepGrass = Clips("footstep_grass_", 4);
            am.footstepGlass = Clips("footstep_glass_", 4);
            am.bubbleNotes = Clips("bubble_", 8);
            string[] ids =
            {
                "bubble_drop", "pulse", "dash", "clam_open", "shard_pickup", "beacon_light", "beacon_denied",
                "bridge_tile", "bridge_complete", "pylon_activate", "cube_push", "cube_reset", "pad_on", "pad_off",
                "gate_open", "lantern_light", "jelly_hit", "jelly_repel", "portal_open", "portal_enter",
                "zone_enter", "ui_hover", "ui_click", "ui_open", "ui_close"
            };
            var quiet = new Dictionary<string, float> { { "ui_hover", 0.5f }, { "bridge_tile", 0.7f } };
            foreach (var id in ids)
            {
                var clip = AssetDatabase.LoadAssetAtPath<AudioClip>(Root + "Audio/SFX/" + id + ".wav");
                if (clip == null) continue;
                am.clips.Add(new AquaScape.AudioManager.NamedClip { id = id, clip = clip, volume = quiet.TryGetValue(id, out var v) ? v : 1f });
            }

            var music = audio.AddComponent<AquaScape.MusicDirector>();
            AudioClip M(string n) => AssetDatabase.LoadAssetAtPath<AudioClip>(Root + "Audio/Music/" + n + ".wav");
            music.pad = M("music_pad");
            music.nightPad = M("music_night");
            music.keys = M("music_keys");
            music.arp = M("music_arp");
            music.melody = M("music_melody");
            music.completeJingle = M("jingle_complete");
            music.oceanAmbience = M("amb_ocean");
            music.cityAmbience = M("amb_city");
            music.nightAmbience = M("amb_night");
        }

        static AudioClip[] Clips(string prefix, int count)
        {
            var list = new List<AudioClip>();
            for (int i = 1; i <= count; i++)
            {
                var c = AssetDatabase.LoadAssetAtPath<AudioClip>(Root + "Audio/SFX/" + prefix + i + ".wav");
                if (c != null) list.Add(c);
            }
            return list.ToArray();
        }

        static void BuildUI()
        {
            var es = new GameObject("EventSystem", typeof(UnityEngine.EventSystems.EventSystem), typeof(InputSystemUIInputModule));
            var ui = new GameObject("UI", typeof(RectTransform));
            var mgr = ui.AddComponent<AquaScape.UIManager>();
            ui.AddComponent<AquaScape.TutorialHints>();
            mgr.font = BuildFontAsset();
            mgr.panelSprite = LoadSprite("UI/panel");
            mgr.buttonSprite = LoadSprite("UI/button");
            mgr.buttonHoverSprite = LoadSprite("UI/button_hover");
            mgr.pillSprite = LoadSprite("UI/pill");
            mgr.logoSprite = LoadSprite("UI/logo");
            mgr.iconBubble = LoadSprite("UI/icon_bubble");
            mgr.iconShard = LoadSprite("UI/icon_shard");
            mgr.iconBeaconOff = LoadSprite("UI/icon_beacon_off");
            mgr.iconBeaconOn = LoadSprite("UI/icon_beacon_on");
            mgr.completeBackground = LoadSprite("UI/complete_bg");
        }

        static TMP_FontAsset BuildFontAsset()
        {
            string path = Root + "Fonts/MPLUSRounded_SDF.asset";
            var existing = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(path);
            if (existing != null) return existing;
            var font = AssetDatabase.LoadAssetAtPath<Font>(Root + "Fonts/MPLUSRounded1c-ExtraBold.ttf");
            var fa = TMP_FontAsset.CreateFontAsset(font, 90, 9, UnityEngine.TextCore.LowLevel.GlyphRenderMode.SDFAA, 1024, 1024,
                AtlasPopulationMode.Dynamic, true);
            fa.name = "MPLUSRounded_SDF";
            AssetDatabase.CreateAsset(fa, path);
            foreach (var tex in fa.atlasTextures)
            {
                tex.name = "MPLUSRounded Atlas";
                AssetDatabase.AddObjectToAsset(tex, fa);
            }
            fa.material.name = "MPLUSRounded Material";
            AssetDatabase.AddObjectToAsset(fa.material, fa);
            EditorUtility.SetDirty(fa);
            AssetDatabase.SaveAssets();
            return fa;
        }

        // =====================================================================
        // Helpers
        // =====================================================================

        public static Sprite LoadSprite(string relPath)
        {
            string p = Art + relPath + ".png";
            var s = AssetDatabase.LoadAssetAtPath<Sprite>(p);
            if (s == null) Debug.LogWarning("[AquaScape] Missing sprite " + p);
            return s;
        }

        public static Sprite[] LoadFrames(string prefix, int count)
        {
            var list = new List<Sprite>();
            for (int i = 0; i < count; i++)
            {
                var s = AssetDatabase.LoadAssetAtPath<Sprite>(Art + prefix + i + ".png");
                if (s != null) list.Add(s);
            }
            return list.ToArray();
        }

        static InputActionReference ActionRef(string map, string action)
        {
            foreach (var o in AssetDatabase.LoadAllAssetsAtPath("Assets/Settings/InputSystem_Actions.inputactions"))
                if (o is InputActionReference r && r.action != null && r.action.name == action && r.action.actionMap.name == map)
                    return r;
            Debug.LogWarning($"[AquaScape] Missing input action {map}/{action}");
            return null;
        }
    }
}
