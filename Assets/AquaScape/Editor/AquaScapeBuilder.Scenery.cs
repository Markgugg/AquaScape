using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape.EditorTools
{
    /// <summary>
    /// The scenery pass: far horizon panoramas, one hero landmark per area,
    /// water-surface details and ambient wildlife (fish in the water, glassy
    /// fish swimming through the air, butterflies).
    /// </summary>
    public static partial class AquaScapeBuilder
    {
        const float HorizonY = 34.5f;   // must match _HorizonY on the water material

        static void BuildScenery()
        {
            var root = new GameObject("Scenery").transform;
            var unlit = AssetDatabase.LoadAssetAtPath<Material>(
                "Packages/com.unity.render-pipelines.universal/Runtime/Materials/Sprite-Unlit-Default.mat");
            var rng = new System.Random(4242);
            float R(float a, float b) => a + (float)rng.NextDouble() * (b - a);

            // ---- far horizon panoramas (one per area, crossfaded by zone)
            string[] names = { "backdrop_lagoon", "backdrop_city", "backdrop_moon" };
            float[] anchors = { 20f, 60f, 100f };
            for (int i = 0; i < 3; i++)
            {
                var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(Art + "Backgrounds/" + names[i] + ".png");
                if (sprite == null) continue;
                var go = new GameObject(names[i], typeof(SpriteRenderer));
                go.transform.SetParent(root);
                var sr = go.GetComponent<SpriteRenderer>();
                sr.sprite = sprite;
                sr.sharedMaterial = unlit;           // painted lighting, ignore the 2D lights
                sr.sortingLayerName = "Water";
                sr.sortingOrder = 5 + i;
                const float scale = 1.4f;
                go.transform.localScale = Vector3.one * scale;
                // horizon sits 75% down the image; place it on HorizonY
                float h = sprite.bounds.size.y * scale;
                go.transform.position = new Vector3(anchors[i], HorizonY + 0.25f * h, 0f);
                var hb = go.AddComponent<AquaScape.HorizonBackdrop>();
                hb.anchorX = anchors[i];
                hb.zone = i;
            }

            // ---- hero landmarks
            // Blue Lagoon: floating island with a waterfall, near the north shore
            var isle = Setpiece(root, "FloatingIsle", "Scenery/floating_isle", new Vector3(33.5f, 23.2f, 0));
            if (isle != null)
            {
                var fall = SpriteChild(isle.transform, "Waterfall", "Scenery/floating_isle_fall_0", "Objects", Vector3.zero);
                fall.sortingOrder = 1;
                var fb = fall.gameObject.AddComponent<AquaScape.SpinFake3D>();
                fb.mode = AquaScape.SpinFake3D.Mode.Flipbook;
                fb.frames = LoadFrames("Scenery/floating_isle_fall_", 4);
                fb.speed = 8f;
                var bob = isle.AddComponent<AquaScape.Bobbing>();
                bob.amplitude = 0.08f;
                bob.frequency = 0.6f;
            }
            // Glass City: glass domes on the water, a needle tower and floating rings
            Setpiece(root, "GlassDomes", "Scenery/domes", new Vector3(57f, 2.6f, 0));
            Setpiece(root, "NeedleTower", "Scenery/needle_tower", new Vector3(77.5f, 22.4f, 0));
            foreach (var pos in new[] { new Vector3(46f, 25.5f, 0), new Vector3(64.5f, 22.5f, 0), new Vector3(63.5f, 5f, 0) })
            {
                var ring = SpriteChild(root, "ChromeRing", "Scenery/chrome_ring", "Overhead", pos);
                ring.sortingOrder = -5;
                ring.gameObject.AddComponent<AquaScape.SpinFake3D>().speed = 0.5f;
                ring.gameObject.AddComponent<AquaScape.Bobbing>().amplitude = 0.15f;
            }
            // Moonpool: glowing crystals floating over the night water
            foreach (var pos in new[] { new Vector3(88f, 23f, 0), new Vector3(106.5f, 24f, 0), new Vector3(111f, 11.5f, 0),
                                        new Vector3(91.5f, 8.5f, 0), new Vector3(118f, 10f, 0), new Vector3(101f, 27.5f, 0) })
            {
                var c = SpriteChild(root, "Crystal", "Scenery/crystal_1", "Objects", pos);
                c.transform.localScale = Vector3.one * R(0.8f, 1.2f);
                var bob = c.gameObject.AddComponent<AquaScape.Bobbing>();
                bob.amplitude = 0.2f;
                bob.frequency = R(0.6f, 1f);
                PointLight(c.transform, Vector3.zero, new Color(0.7f, 0.6f, 1f), 3f, 0.9f);
            }

            // ---- lily pads along the lagoon shores (open water next to land)
            var terrain = Object.FindAnyObjectByType<AquaScape.TerrainPainter>();
            int pads = 0;
            for (int tries = 0; tries < 2000 && pads < 22; tries++)
            {
                int x = rng.Next(0, 38), y = rng.Next(0, s_h);
                var cell = new Vector3Int(x, y, 0);
                if (terrain.IsWalkable(cell) || char.IsDigit(At(x, y))) continue;
                bool nearLand = false, nearCliff = terrain.IsWalkable(cell + Vector3Int.up);
                for (int dy = -2; dy <= 2; dy++)
                    for (int dx = -2; dx <= 2; dx++)
                        if (terrain.IsWalkable(cell + new Vector3Int(dx, dy, 0))) nearLand = true;
                if (!nearLand || nearCliff) continue;
                var lp = SpriteChild(root, "LilyPad", "Scenery/lilypad_1", "Underwater", new Vector3(x + R(0.2f, 0.8f), y + R(0.2f, 0.8f), 0));
                lp.sortingOrder = 10;
                lp.spriteSortPoint = SpriteSortPoint.Center;
                lp.transform.rotation = Quaternion.Euler(0, 0, R(0, 360));
                lp.transform.localScale = Vector3.one * R(0.7f, 1.1f);
                pads++;
            }

            // ---- wildlife
            string[] waterFish = { "koi_orange", "koi_white", "fish_yellow", "fish_blue", "koi_orange", "fish_yellow" };
            for (int i = 0; i < 34; i++)
            {
                string kind = waterFish[i % waterFish.Length];
                var frames = LoadFrames($"Creatures/{kind}_", 4);
                if (frames.Length == 0) continue;
                var go = new GameObject("Fish_" + kind);
                go.transform.SetParent(root);
                go.transform.position = new Vector3(R(0, 118), R(0, 33), 0);
                var sr = SpriteChild(go.transform, "Body", $"Creatures/{kind}_0", "Underwater", Vector3.zero);
                sr.spriteSortPoint = SpriteSortPoint.Center;
                go.transform.localScale = Vector3.one * R(0.75f, 1.05f);
                var sw = go.AddComponent<AquaScape.Swimmer>();
                sw.medium = AquaScape.Swimmer.Medium.Water;
                sw.frames = frames;
                sw.fps = 7f;
                sw.speed = R(0.7f, 1.4f);
                sw.dayAlpha = 0.7f;
                sw.nightAlpha = 0.3f;
                sw.area = new Rect(-2, -2, s_w + 4, s_h + 2);
            }
            AirCreatures(root, "skyfish_aqua", 4, 1.9f, 0.9f, R);
            AirCreatures(root, "skyfish_koi", 4, 2.3f, 0.8f, R);
            AirCreatures(root, "butterfly", 7, 0.9f, 0.9f, R, 10f, new Rect(0, 2, 75, 28));
        }

        static void AirCreatures(Transform root, string kind, int count, float height, float speed,
            System.Func<float, float, float> R, float fps = 6f, Rect? area = null)
        {
            var frames = LoadFrames($"Creatures/{kind}_", 4);
            if (frames.Length == 0) return;
            for (int i = 0; i < count; i++)
            {
                var go = new GameObject("Sky_" + kind);
                go.transform.SetParent(root);
                go.transform.position = new Vector3(R(0, 118), R(2, 31), 0);
                var shadow = Shadow(go.transform, kind == "butterfly" ? 0.3f : 0.9f, 0.2f);
                var sr = SpriteChild(go.transform, "Body", $"Creatures/{kind}_0", "Overhead", new Vector3(0, height, 0));
                sr.sortingOrder = -2;
                var sw = go.AddComponent<AquaScape.Swimmer>();
                sw.medium = AquaScape.Swimmer.Medium.Air;
                sw.frames = frames;
                sw.fps = fps;
                sw.speed = speed * R(0.8f, 1.2f);
                sw.hoverHeight = height;
                sw.shadow = shadow;
                sw.dayAlpha = 0.95f;
                sw.nightAlpha = 0.8f;
                sw.area = area ?? new Rect(0, 0, s_w, s_h);
            }
        }

        static GameObject Setpiece(Transform root, string name, string sprite, Vector3 pos)
        {
            if (AssetDatabase.LoadAssetAtPath<Sprite>(Art + sprite + ".png") == null)
            {
                Debug.LogWarning("[AquaScape] Missing setpiece " + sprite);
                return null;
            }
            var go = new GameObject(name);
            go.transform.SetParent(root);
            go.transform.position = pos;
            var vis = SpriteChild(go.transform, "Visual", sprite, "Objects", Vector3.zero);
            Reflect(go.transform, vis);
            return go;
        }
    }
}
