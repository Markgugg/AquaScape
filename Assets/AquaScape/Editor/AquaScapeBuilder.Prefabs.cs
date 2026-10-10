using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace AquaScape.EditorTools
{
    // materials, particle effects, prefabs and the player
    public static partial class AquaScapeBuilder
    {
        // materials

        // all the materials the builder makes
        class Materials
        {
            public Material water, glowAdd, dotAlpha, sparkleAdd, bubbleAlpha, starAdd, ringAdd;
        }

        // makes the water and particle materials
        static Materials BuildMaterials()
        {
            var m = new Materials();
            m.water = Mat("AquaWater", Shader.Find("AquaScape/Water"), null);
            var particle = Shader.Find("AquaScape/Particle");
            m.glowAdd = Mat("FxSoftAdd", particle, Tex("FX/soft_dot"), true);
            m.dotAlpha = Mat("FxSoftAlpha", particle, Tex("FX/soft_dot"), false);
            m.sparkleAdd = Mat("FxSparkleAdd", particle, Tex("FX/sparkle"), true);
            m.bubbleAlpha = Mat("FxBubble", particle, Tex("FX/bubble_small"), false);
            m.starAdd = Mat("FxStarAdd", particle, Tex("FX/star"), true);
            m.ringAdd = Mat("FxRingAdd", particle, Tex("FX/ring"), true);
            return m;
        }

        // loads a texture from the art folder
        static Texture2D Tex(string rel) => AssetDatabase.LoadAssetAtPath<Texture2D>(Art + rel + ".png");

        // loads or makes a material and sets how it blends
        static Material Mat(string name, Shader shader, Texture tex, bool additive = false)
        {
            string path = Root + "Materials/" + name + ".mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(shader);
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.shader = shader;
            if (tex != null) mat.SetTexture("_MainTex", tex);
            if (mat.HasProperty("_SrcBlend"))
            {
                mat.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
                mat.SetFloat("_DstBlend", (float)(additive ? BlendMode.One : BlendMode.OneMinusSrcAlpha));
            }
            EditorUtility.SetDirty(mat);
            return mat;
        }

        // particle effects

        // all the particle prefabs
        class Fx
        {
            public ParticleSystem pop, sparkle, tile, poof, dashTrail, footDust, pulseBurst, dayMotes, fireflies, beaconSparkles, portalMotes;
        }

        // makes all the particle prefabs
        static Fx BuildParticlePrefabs(Materials m)
        {
            var fx = new Fx();
            // one shot bursts
            fx.pop = SavePs("FX_BubblePop", Burst(m.bubbleAlpha, 10, 0.25f, 0.5f, 1.8f, 0.12f, 0.22f, new Color(0.8f, 1f, 1f, 0.9f), true, -0.3f));
            fx.sparkle = SavePs("FX_Sparkle", Burst(m.sparkleAdd, 18, 0.5f, 0.9f, 2.6f, 0.2f, 0.45f, new Color(0.7f, 0.98f, 1f), true, -0.2f));
            fx.tile = SavePs("FX_TileSparkle", Burst(m.sparkleAdd, 6, 0.35f, 0.6f, 1.2f, 0.15f, 0.35f, new Color(0.75f, 1f, 1f), true, -0.4f));
            fx.poof = SavePs("FX_Poof", Burst(m.dotAlpha, 16, 0.4f, 0.7f, 1.5f, 0.35f, 0.7f, new Color(0.9f, 0.97f, 1f, 0.8f), true, 0f));

            // player effects
            fx.dashTrail = SavePs("FX_DashTrail", Burst(m.bubbleAlpha, 0, 0.3f, 0.6f, 0.6f, 0.1f, 0.25f, new Color(0.85f, 1f, 1f, 0.9f), false, -0.5f));
            fx.footDust = SavePs("FX_FootDust", Burst(m.dotAlpha, 0, 0.3f, 0.5f, 0.4f, 0.12f, 0.22f, new Color(1f, 1f, 1f, 0.55f), false, -0.1f));
            fx.pulseBurst = SavePs("FX_PulseBurst", Burst(m.bubbleAlpha, 0, 0.4f, 0.7f, 4.2f, 0.1f, 0.22f, new Color(0.8f, 1f, 1f, 0.95f), false, 0f));

            // ambient effects
            fx.dayMotes = SavePs("FX_DayMotes", Ambient(m.sparkleAdd, new Color(1f, 1f, 0.95f, 0.8f), 0.06f, 0.14f, new Vector2(0.15f, 0.25f)));
            fx.fireflies = SavePs("FX_Fireflies", Ambient(m.glowAdd, new Color(0.55f, 0.95f, 1f, 1f), 0.08f, 0.2f, new Vector2(0.05f, 0.18f)));

            // rising columns
            fx.beaconSparkles = SavePs("FX_BeaconSparkles", Column(m.sparkleAdd, new Color(0.7f, 1f, 1f), 7f, 3.5f));
            fx.portalMotes = SavePs("FX_PortalMotes", Column(m.starAdd, new Color(0.85f, 0.85f, 1f), 9f, 1.8f));
            return fx;
        }

        // makes an empty particle system on the fx layer
        static ParticleSystem NewPs(string name, Material mat)
        {
            var go = new GameObject(name, typeof(ParticleSystem));
            var ps = go.GetComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.sortingLayerName = "FX";
            return ps;
        }

        // a burst of particles for pops, sparkles and trails
        static ParticleSystem Burst(Material mat, int count, float lifeMin, float lifeMax, float speed, float sizeMin, float sizeMax,
            Color color, bool oneShot, float gravity)
        {
            var ps = NewPs("burst", mat);
            var main = ps.main;
            main.duration = 1f;
            main.loop = false;
            main.playOnAwake = oneShot;
            main.startLifetime = new ParticleSystem.MinMaxCurve(lifeMin, lifeMax);
            main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.4f, speed);
            main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
            main.startColor = color;
            main.gravityModifier = gravity;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.stopAction = oneShot ? ParticleSystemStopAction.Destroy : ParticleSystemStopAction.None;
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            var em = ps.emission;
            em.rateOverTime = 0f;
            if (count > 0) em.SetBursts(new[] { new ParticleSystem.Burst(0f, (short)count) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Circle;
            shape.radius = 0.15f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = FadeOut();
            var size = ps.sizeOverLifetime;
            size.enabled = true;
            size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 1, 1, 0.3f));
            var limit = ps.limitVelocityOverLifetime;
            limit.enabled = true;
            limit.dampen = 0.15f;
            limit.limit = 0.2f;
            return ps;
        }

        // floating particles spread over the whole view
        static ParticleSystem Ambient(Material mat, Color color, float sizeMin, float sizeMax, Vector2 drift)
        {
            var ps = NewPs("ambient", mat);
            var main = ps.main;
            main.loop = true;
            main.duration = 5f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(4f, 7f);
            main.startSpeed = 0f;
            main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
            main.startColor = color;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 300;
            var em = ps.emission;
            em.rateOverTime = 5f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(26f, 15f, 1f);
            var vel = ps.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(-drift.x, drift.x);
            vel.y = new ParticleSystem.MinMaxCurve(-drift.x * 0.3f, drift.y);
            vel.z = new ParticleSystem.MinMaxCurve(0f, 0f);
            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = 0.25f;
            noise.frequency = 0.3f;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = FadeInOut();
            ps.GetComponent<ParticleSystemRenderer>().sortingLayerName = "Overhead";
            return ps;
        }

        // a rising column of sparkles for the beacon and the portal
        static ParticleSystem Column(Material mat, Color color, float rate, float height)
        {
            var ps = NewPs("column", mat);
            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(1.2f, 2f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(height * 0.4f, height * 0.7f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.08f, 0.22f);
            main.startColor = color;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission;
            em.rateOverTime = rate;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 8f;
            shape.radius = 0.35f;
            shape.rotation = new Vector3(-90f, 0f, 0f);
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = FadeInOut();
            return ps;
        }

        // fades particles out at the end
        static Gradient FadeOut()
        {
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.8f, 0.5f), new GradientAlphaKey(0f, 1f) });
            return g;
        }

        // fades particles in and then out
        static Gradient FadeInOut()
        {
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.25f), new GradientAlphaKey(1f, 0.7f), new GradientAlphaKey(0f, 1f) });
            return g;
        }

        // saves a particle system as a prefab
        static ParticleSystem SavePs(string name, ParticleSystem ps)
        {
            ps.gameObject.name = name;
            var prefab = PrefabUtility.SaveAsPrefabAsset(ps.gameObject, Root + "Prefabs/" + name + ".prefab");
            Object.DestroyImmediate(ps.gameObject);
            return prefab.GetComponent<ParticleSystem>();
        }

        // prefabs

        // all the prefabs the level uses
        class Prefabs
        {
            public GameObject bubble, clam, pylon, beacon, shard, cube, pad, gatePanel, lantern, jelly, portal;
            public Dictionary<char, GameObject[]> decor = new Dictionary<char, GameObject[]>();
        }

        // makes all the gameplay and decor prefabs
        static Prefabs BuildPrefabs(Materials m, Fx fx)
        {
            var p = new Prefabs();

            // decor props with an optional small collider at the base
            p.decor['T'] = new[] { Decor("Palm_1", "Props/palm_1", 0.22f), Decor("Palm_2", "Props/palm_2", 0.22f) };
            p.decor['t'] = new[] { Decor("Bush_1", "Props/bush_1", 0.38f), Decor("Bush_2", "Props/bush_2", 0.38f) };
            p.decor['f'] = new[] { Decor("Flowers_1", "Props/flowers_1", 0f), Decor("Flowers_2", "Props/flowers_2", 0f) };
            p.decor['e'] = new[] { Decor("Fern", "Props/fern_1", 0f) };
            p.decor['r'] = new[] { Decor("Rock_1", "Props/rock_1", 0.32f), Decor("Rock_2", "Props/rock_2", 0.32f) };
            p.decor['l'] = new[] { Decor("Lamp", "Props/lamp", 0.14f, new Color(0.7f, 0.97f, 1f), 1.75f) };
            p.decor['k'] = new[] { Decor("Spire_1", "Props/spire_1", 0.4f), Decor("Spire_2", "Props/spire_2", 0.4f) };
            p.decor['A'] = new[] { Decor("Arch", "Props/arch", 0f) };
            p.decor['n'] = new[] { Decor("NightFlower", "Props/nightflower", 0f, new Color(0.6f, 0.6f, 1f), 0.5f) };

            // bubble
            {
                var go = new GameObject("Bubble");
                Shadow(go.transform, 0.45f, 0.35f);
                var vis = SpriteChild(go.transform, "Visual", "FX/bubble", "Objects", new Vector3(0, 0.35f, 0));
                vis.transform.localScale = Vector3.one * 0.85f;
                var b = go.AddComponent<AquaScape.Bubble>();
                b.visual = vis.transform;
                b.sprite = vis;
                p.bubble = Save(go, "Bubble");
            }
            // clam
            {
                var go = new GameObject("BubbleClam");
                var sr = SpriteChild(go.transform, "Visual", "Props/bubble_clam_closed", "Objects", Vector3.zero);
                Collider(go, 0.42f);
                var c = go.AddComponent<AquaScape.BubbleClam>();
                c.sprite = sr;
                c.openSprite = LoadSprite("Props/bubble_clam_open");
                c.promptOffset = new Vector3(0, 1.3f, 0);
                p.clam = Save(go, "BubbleClam");
            }
            // pylon
            {
                var go = new GameObject("BridgePylon");
                var sr = SpriteChild(go.transform, "Visual", "Props/pylon_off", "Objects", Vector3.zero);
                Collider(go, 0.3f);
                var py = go.AddComponent<AquaScape.BridgePylon>();
                py.sprite = sr;
                Reflect(go.transform, sr);
                py.onSprite = LoadSprite("Props/pylon_on");
                py.glow = PointLight(go.transform, new Vector3(0, 1.3f, 0), new Color(0.75f, 0.9f, 1f), 1.8f, 0.25f);
                py.promptOffset = new Vector3(0, 2.1f, 0);
                p.pylon = Save(go, "BridgePylon");
            }
            // beacon
            {
                var go = new GameObject("Beacon");
                var sr = SpriteChild(go.transform, "Visual", "Props/beacon_off", "Objects", Vector3.zero);
                Collider(go, 0.65f);
                var bc = go.AddComponent<AquaScape.Beacon>();
                bc.sprite = sr;
                Reflect(go.transform, sr);
                bc.litSprite = LoadSprite("Props/beacon_on");
                bc.glow = PointLight(go.transform, new Vector3(0, 2.5f, 0), new Color(0.55f, 0.95f, 1f), 6f, 0.4f);
                var spark = (ParticleSystem)PrefabUtility.InstantiatePrefab(fx.beaconSparkles, go.transform);
                spark.transform.localPosition = new Vector3(0, 2.4f, 0);
                bc.sparkles = spark;
                bc.promptOffset = new Vector3(0, 3.6f, 0);
                bc.reachBonus = 0.6f;
                p.beacon = Save(go, "Beacon");
            }
            // shard
            {
                var go = new GameObject("PrismShard");
                Shadow(go.transform, 0.5f, 0.4f);
                var vis = SpriteChild(go.transform, "Visual", "Props/shard", "Objects", new Vector3(0, 0.55f, 0));
                PointLight(vis.transform, Vector3.zero, new Color(0.4f, 0.75f, 1f), 2.2f, 1.1f);
                var s = go.AddComponent<AquaScape.PrismShard>();
                s.visual = vis.transform;
                p.shard = Save(go, "PrismShard");
            }
            // glass cube
            {
                var go = new GameObject("GlassCube");
                var sr = SpriteChild(go.transform, "Visual", "Props/cube", "Objects", Vector3.zero);
                var rb = go.AddComponent<Rigidbody2D>();
                rb.bodyType = RigidbodyType2D.Kinematic;
                rb.interpolation = RigidbodyInterpolation2D.Interpolate;
                var box = go.AddComponent<BoxCollider2D>();
                box.size = new Vector2(0.86f, 0.7f);
                box.offset = new Vector2(0, 0.38f);
                var cube = go.AddComponent<AquaScape.GlassCube>();
                cube.sprite = sr;
                cube.promptOffset = new Vector3(0, 1.5f, 0);
                p.cube = Save(go, "GlassCube");
            }
            // pressure pad
            {
                var go = new GameObject("PressurePad");
                var sr = SpriteChild(go.transform, "Visual", "Props/pad_off", "Ground", Vector3.zero);
                sr.sortingOrder = 5;
                var pad = go.AddComponent<AquaScape.PressurePad>();
                pad.sprite = sr;
                pad.onSprite = LoadSprite("Props/pad_on");
                pad.glow = PointLight(go.transform, new Vector3(0, 0.1f, 0), new Color(0.5f, 0.95f, 1f), 1.6f, 0f);
                p.pad = Save(go, "PressurePad");
            }
            // gate panel
            {
                var go = new GameObject("GatePanel");
                SpriteChild(go.transform, "Visual", "Props/gate", "Objects", Vector3.zero);
                var box = go.AddComponent<BoxCollider2D>();
                box.size = new Vector2(1f, 0.6f);
                box.offset = new Vector2(0, 0.3f);
                p.gatePanel = Save(go, "GatePanel");
            }
            // moon lantern
            {
                var go = new GameObject("MoonLantern");
                var sr = SpriteChild(go.transform, "Visual", "Props/lantern_off", "Objects", Vector3.zero);
                Collider(go, 0.2f);
                var l = go.AddComponent<AquaScape.MoonLantern>();
                l.sprite = sr;
                Reflect(go.transform, sr);
                l.litSprite = LoadSprite("Props/lantern_on");
                l.glow = PointLight(go.transform, new Vector3(0, 1.5f, 0), new Color(0.75f, 0.75f, 1f), 4f, 0f);
                l.promptOffset = new Vector3(0, 2.4f, 0);
                p.lantern = Save(go, "MoonLantern");
            }
            // jellyfish
            {
                var go = new GameObject("Jellyfish");
                var shadow = Shadow(go.transform, 0.6f, 0.3f);
                var sr = SpriteChild(go.transform, "Visual", "Props/jelly_0", "Objects", new Vector3(0, 0.9f, 0));
                var j = go.AddComponent<AquaScape.Jellyfish>();
                j.sprite = sr;
                j.frames = LoadFrames("Props/jelly_", 4);
                j.shadow = shadow;
                j.glow = PointLight(sr.transform, Vector3.zero, new Color(0.85f, 0.5f, 1f), 2f, 0.9f);
                p.jelly = Save(go, "Jellyfish");
            }
            // moonpool portal
            {
                var go = new GameObject("MoonpoolPortal");
                var sr = SpriteChild(go.transform, "Visual", "Props/portal_off", "Ground", Vector3.zero);
                sr.sortingOrder = 5;
                var portal = go.AddComponent<AquaScape.MoonpoolPortal>();
                portal.sprite = sr;
                portal.activeSprite = LoadSprite("Props/portal_on");
                portal.glow = PointLight(go.transform, new Vector3(0, 0.2f, 0), new Color(0.6f, 0.75f, 1f), 4.5f, 0f);
                var motes = (ParticleSystem)PrefabUtility.InstantiatePrefab(fx.portalMotes, go.transform);
                portal.motes = motes;
                p.portal = Save(go, "MoonpoolPortal");
            }
            return p;
        }

        // makes a decor prop, tall ones get a reflection and plants sway
        static GameObject Decor(string name, string sprite, float colliderRadius, Color? glowColor = null, float glowHeight = 0f)
        {
            var go = new GameObject(name);
            var vis = SpriteChild(go.transform, "Visual", sprite, "Objects", Vector3.zero);
            bool tall = name.StartsWith("Palm") || name.StartsWith("Spire") || name == "Lamp" || name == "Arch";
            if (tall) Reflect(go.transform, vis);
            if (name.StartsWith("Palm")) vis.gameObject.AddComponent<AquaScape.WindSway>();
            if (name.StartsWith("Bush") || name.StartsWith("Fern"))
            {
                var sway = vis.gameObject.AddComponent<AquaScape.WindSway>();
                sway.degrees = 1.2f;
                sway.speed = 1.3f;
            }
            if (colliderRadius > 0f) Collider(go, colliderRadius);
            if (glowColor.HasValue) PointLight(go.transform, new Vector3(0, glowHeight, 0), glowColor.Value, 2.4f, 0.8f);
            return Save(go, name);
        }

        // adds a rippling mirror image on the water under a tall sprite
        static void Reflect(Transform parent, SpriteRenderer source)
        {
            if (source == null || source.sprite == null) return;
            var r = SpriteChild(parent, "Reflection", null, "Underwater", Vector3.zero);
            r.sprite = source.sprite;
            r.sortingOrder = 20;
            r.spriteSortPoint = SpriteSortPoint.Center;
            r.gameObject.AddComponent<AquaScape.WaterReflection>().source = source;
        }

        // makes a child object with a sprite on it
        static SpriteRenderer SpriteChild(Transform parent, string name, string sprite, string layer, Vector3 pos)
        {
            var go = new GameObject(name, typeof(SpriteRenderer));
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            var sr = go.GetComponent<SpriteRenderer>();
            if (sprite != null) sr.sprite = LoadSprite(sprite);
            sr.sortingLayerName = layer;
            sr.spriteSortPoint = SpriteSortPoint.Pivot;
            return sr;
        }

        // adds a soft shadow under a floating thing
        static Transform Shadow(Transform parent, float width, float alpha)
        {
            var sr = SpriteChild(parent, "Shadow", "Props/float_shadow", "Ground", Vector3.zero);
            sr.sortingOrder = 10;
            sr.color = new Color(1, 1, 1, alpha);
            float native = sr.sprite != null ? sr.sprite.bounds.size.x : 1f;
            sr.transform.localScale = Vector3.one * (width / Mathf.Max(0.01f, native));
            var holder = new GameObject("ShadowRoot").transform;
            holder.SetParent(parent, false);
            sr.transform.SetParent(holder, true);
            return holder;
        }

        // adds a small circle collider at the base
        static void Collider(GameObject go, float radius)
        {
            var c = go.AddComponent<CircleCollider2D>();
            c.radius = radius;
            c.offset = new Vector2(0, radius * 0.5f);
        }

        // adds a glowing point light
        static Light2D PointLight(Transform parent, Vector3 pos, Color color, float radius, float intensity)
        {
            var go = new GameObject("Glow", typeof(Light2D));
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            var l = go.GetComponent<Light2D>();
            l.lightType = Light2D.LightType.Point;
            l.color = color;
            l.intensity = intensity;
            l.pointLightOuterRadius = radius;
            l.pointLightInnerRadius = radius * 0.1f;
            l.falloffIntensity = 0.7f;
            TargetAllLayers(l);
            return l;
        }

        // saves an object as a prefab and deletes the scene copy
        static GameObject Save(GameObject go, string name)
        {
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, Root + "Prefabs/" + name + ".prefab");
            Object.DestroyImmediate(go);
            return prefab;
        }

        // places a prefab in the scene
        static GameObject Spawn(GameObject prefab, Vector3 pos, Transform parent)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
            go.transform.position = pos;
            return go;
        }

        // player

        // makes the player animator with idle and walk
        static AnimatorController BuildPlayerAnimator()
        {
            string path = Root + "Animations/Aqua.controller";
            AssetDatabase.DeleteAsset(path);
            var ctrl = AnimatorController.CreateAnimatorControllerAtPath(path);
            ctrl.AddParameter("FaceX", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("FaceY", AnimatorControllerParameterType.Float);
            ctrl.AddParameter("Speed", AnimatorControllerParameterType.Float);

            // makes one looping clip from the frames
            AnimationClip Clip(string anim, string dir, float fps, bool footsteps)
            {
                var frames = LoadFrames($"Character/{anim}_{dir}_", 8);
                var clip = new AnimationClip { frameRate = fps, name = $"{anim}_{dir}" };
                var binding = EditorCurveBinding.PPtrCurve("Visual", typeof(SpriteRenderer), "m_Sprite");
                var keys = new ObjectReferenceKeyframe[frames.Length + 1];
                for (int i = 0; i <= frames.Length; i++)
                    keys[i] = new ObjectReferenceKeyframe { time = i / fps, value = frames[i % frames.Length] };
                AnimationUtility.SetObjectReferenceCurve(clip, binding, keys);
                var settings = AnimationUtility.GetAnimationClipSettings(clip);
                settings.loopTime = true;
                AnimationUtility.SetAnimationClipSettings(clip, settings);
                if (footsteps)
                {
                    // feet touch down on frames 0 and 4 of the 8 frame cycle
                    AnimationUtility.SetAnimationEvents(clip, new[]
                    {
                        new AnimationEvent { time = 0.01f, functionName = "Footstep" },
                        new AnimationEvent { time = 4f / fps, functionName = "Footstep" },
                    });
                }
                string clipPath = Root + $"Animations/{anim}_{dir}.anim";
                AssetDatabase.DeleteAsset(clipPath);
                AssetDatabase.CreateAsset(clip, clipPath);
                return clip;
            }

            // makes a blend tree for down, up and side
            AnimatorState Tree(string name, string anim, float fps, bool footsteps)
            {
                var state = ctrl.CreateBlendTreeInController(name, out var tree, 0);
                tree.blendType = BlendTreeType.SimpleDirectional2D;
                tree.blendParameter = "FaceX";
                tree.blendParameterY = "FaceY";
                tree.AddChild(Clip(anim, "down", fps, footsteps), new Vector2(0, -1));
                tree.AddChild(Clip(anim, "up", fps, footsteps), new Vector2(0, 1));
                tree.AddChild(Clip(anim, "side", fps, footsteps), new Vector2(1, 0));
                return state;
            }

            // switch between idle and walk by speed
            var idle = Tree("Idle", "idle", 8f, false);
            var walk = Tree("Walk", "walk", 14f, true);
            var sm = ctrl.layers[0].stateMachine;
            sm.defaultState = idle;
            var toWalk = idle.AddTransition(walk);
            toWalk.hasExitTime = false;
            toWalk.duration = 0f;
            toWalk.AddCondition(AnimatorConditionMode.Greater, 0.35f, "Speed");
            var toIdle = walk.AddTransition(idle);
            toIdle.hasExitTime = false;
            toIdle.duration = 0f;
            toIdle.AddCondition(AnimatorConditionMode.Less, 0.25f, "Speed");
            return ctrl;
        }

        // makes the player with physics, sprites, pulse and controls
        static GameObject BuildPlayer(AnimatorController animator, Materials m, Fx fx, Prefabs prefabs)
        {
            // start where the p is in the map
            Vector3 start = Vector3.zero;
            for (int y = 0; y < s_h; y++)
                for (int x = 0; x < s_w; x++)
                    if (At(x, y) == 'P') start = new Vector3(x + 0.5f, y + 0.3f, 0);

            // physics body
            var go = new GameObject("Player");
            go.transform.position = start;
            var rb = go.AddComponent<Rigidbody2D>();
            rb.gravityScale = 0f;
            rb.freezeRotation = true;
            rb.interpolation = RigidbodyInterpolation2D.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode2D.Continuous;
            var col = go.AddComponent<CircleCollider2D>();
            col.radius = 0.26f;
            col.offset = new Vector2(0, 0.12f);

            // body sprite and animator
            var body = SpriteChild(go.transform, "Visual", "Character/idle_down_0", "Objects", Vector3.zero);
            var anim = go.AddComponent<Animator>();
            anim.runtimeAnimatorController = animator;

            // visor glint
            var glint = SpriteChild(body.transform, "Glint", "FX/glint", "Objects", new Vector3(-0.15f, 1.08f, 0));
            glint.sortingOrder = 2;
            glint.spriteSortPoint = SpriteSortPoint.Center;
            var vg = go.AddComponent<AquaScape.VisorGlint>();
            vg.glint = glint;
            vg.body = body;

            // pulse ring and prompt
            var ring = SpriteChild(go.transform, "PulseRing", "FX/ring", "FX", new Vector3(0, 0.3f, 0));
            ring.sharedMaterial = m.ringAdd;
            var prompt = SpriteChild(null, "PulsePrompt", "FX/prompt_space", "FX", start);
            prompt.transform.localScale = Vector3.one * 0.9f;

            var pulse = go.AddComponent<AquaScape.PlayerPulse>();
            pulse.ring = ring;
            pulse.prompt = prompt;
            pulse.burst = Child(fx.pulseBurst, go.transform, new Vector3(0, 0.4f, 0));

            // movement and input
            var pc = go.AddComponent<AquaScape.PlayerController>();
            pc.moveAction = ActionRef("Player", "Move");
            pc.pulseAction = ActionRef("Player", "Jump");
            pc.dashAction = ActionRef("Player", "Sprint");
            pc.animator = anim;
            pc.body = body;
            pc.visual = body.transform;
            pc.dashTrail = Child(fx.dashTrail, go.transform, new Vector3(0, 0.5f, 0));
            pc.footDust = Child(fx.footDust, go.transform, new Vector3(0, 0.05f, 0));

            // soft helmet lamp, mostly seen at night
            PointLight(go.transform, new Vector3(0, 0.9f, 0), new Color(0.7f, 0.8f, 1f), 3.5f, 0.6f);
            return go;
        }

        // places a particle prefab under a parent
        static ParticleSystem Child(ParticleSystem prefab, Transform parent, Vector3 pos)
        {
            var ps = (ParticleSystem)PrefabUtility.InstantiatePrefab(prefab, parent);
            ps.transform.localPosition = pos;
            return ps;
        }

        // level objects

        // places all the objects from the map
        static void PlaceLevelObjects(Prefabs p, AquaScape.TerrainPainter terrain)
        {
            var root = new GameObject("Level").transform;
            var decorRoot = new GameObject("Decor").transform;
            decorRoot.SetParent(root);
            var rng = new System.Random(1234);

            // things that get wired up after placing
            var beacons = new AquaScape.Beacon[3];
            var pylons = new List<AquaScape.BridgePylon>();
            var pads = new List<AquaScape.PressurePad>();
            var lanterns = new List<AquaScape.MoonLantern>();
            var gateCells = new List<Vector3>();
            AquaScape.MoonpoolPortal portal = null;
            var zd = Object.FindAnyObjectByType<AquaScape.ZoneDirector>();

            // go through every map cell
            for (int y = 0; y < s_h; y++)
                for (int x = 0; x < s_w; x++)
                {
                    char c = At(x, y);
                    // jitter decor a little so it does not look lined up on the grid
                    var jitter = new Vector3((float)rng.NextDouble() * 0.3f - 0.15f, (float)rng.NextDouble() * 0.2f - 0.1f, 0f);
                    Vector3 pos = new Vector3(x + 0.5f, y + 0.35f, 0f);
                    int zone = zd.ZoneAt(pos.x);
                    switch (c)
                    {
                        case 'o': Spawn(p.bubble, pos, root); break;
                        case 'C': Spawn(p.clam, pos, root); break;
                        case 'S': Spawn(p.shard, pos, root).GetComponent<AquaScape.PrismShard>().zone = zone; break;
                        case 'B':
                            var b = Spawn(p.beacon, pos, root).GetComponent<AquaScape.Beacon>();
                            b.zone = zone;
                            beacons[zone] = b;
                            break;
                        case 'Y': pylons.Add(Spawn(p.pylon, pos, root).GetComponent<AquaScape.BridgePylon>()); break;
                        case 'X': Spawn(p.cube, new Vector3(x + 0.5f, y + 0.5f, 0), root); break;
                        case 'O': pads.Add(Spawn(p.pad, new Vector3(x + 0.5f, y + 0.5f, 0), root).GetComponent<AquaScape.PressurePad>()); break;
                        case 'G': gateCells.Add(new Vector3(x + 0.5f, y + 0.2f, 0)); break;
                        case 'L': lanterns.Add(Spawn(p.lantern, pos, root).GetComponent<AquaScape.MoonLantern>()); break;
                        case 'J':
                            var j = Spawn(p.jelly, pos, root).GetComponent<AquaScape.Jellyfish>();
                            j.clockwise = (x + y) % 2 == 0;
                            j.radius = new Vector2(1.6f + (x % 3) * 0.4f, 1.0f + (y % 2) * 0.4f);
                            break;
                        case 'M': portal = Spawn(p.portal, new Vector3(x + 0.5f, y + 0.5f, 0), root).GetComponent<AquaScape.MoonpoolPortal>(); break;
                        default:
                            if (p.decor.TryGetValue(c, out var options))
                                Spawn(options[rng.Next(options.Length)], pos + jitter, decorRoot);
                            break;
                    }
                }

            // bridges are digits in the map
            var bridges = new Dictionary<int, AquaScape.BridgeBuilder>();
            for (int id = 1; id <= 4; id++)
            {
                var cells = new List<Vector2Int>();
                for (int y = 0; y < s_h; y++)
                    for (int x = 0; x < s_w; x++)
                        if (At(x, y) == (char)('0' + id) && !terrain.IsWalkable(new Vector3Int(x, y, 0)))
                            cells.Add(new Vector2Int(x, y));
                if (cells.Count == 0) continue;
                var go = new GameObject($"Bridge_{id}");
                go.transform.SetParent(root);
                var bb = go.AddComponent<AquaScape.BridgeBuilder>();
                bb.cells = cells;
                bridges[id] = bb;
            }
            // sorts bridge cells so they build out from a point
            void Order(int id, Vector3 from)
            {
                if (!bridges.TryGetValue(id, out var bb)) return;
                bb.cells = bb.cells.OrderBy(c => Vector2.Distance(c, from)).ToList();
            }

            // wire up who opens what, see the level gen script
            if (pylons.Count > 0 && bridges.ContainsKey(1))
            {
                pylons[0].bridge = bridges[1];
                Order(1, pylons[0].transform.position);
            }
            if (beacons[0] != null && bridges.ContainsKey(2)) { beacons[0].unlocksBridge = bridges[2]; Order(2, beacons[0].transform.position); }
            if (beacons[1] != null && bridges.ContainsKey(3)) { beacons[1].unlocksBridge = bridges[3]; Order(3, beacons[1].transform.position); }
            if (beacons[2] != null) beacons[2].unlocksPortal = portal;

            // lanterns open the last bridge
            if (lanterns.Count > 0)
            {
                var lg = new GameObject("LanternGroup").AddComponent<AquaScape.LanternGroup>();
                lg.transform.SetParent(root);
                lg.lanterns = lanterns;
                foreach (var l in lanterns) l.group = lg;
                if (bridges.ContainsKey(4)) { lg.bridge = bridges[4]; Order(4, beacons[2] != null ? beacons[2].transform.position : Vector3.zero); }
            }

            // pressure pads open the glass gate
            if (gateCells.Count > 0)
            {
                var gate = new GameObject("GlassGate").AddComponent<AquaScape.GlassGate>();
                gate.transform.SetParent(root);
                gate.pads = pads;
                foreach (var pos in gateCells)
                {
                    var panel = Spawn(p.gatePanel, pos, gate.transform);
                    gate.panels.Add(panel.GetComponentInChildren<SpriteRenderer>());
                }
            }
        }

        // ambience

        // makes the drifting clouds and cloud shadows
        static void BuildAmbience(Fx fx)
        {
            var root = new GameObject("Ambience").transform;
            var rng = new System.Random(77);
            float R(float a, float b) => a + (float)rng.NextDouble() * (b - a);

            // clouds
            for (int i = 0; i < 6; i++)
            {
                var sr = SpriteChild(root, "Cloud", $"FX/cloud_{1 + i % 3}", "Overhead", new Vector3(R(-5, 75), i % 2 == 0 ? R(26, 36) : R(-4, 4), 0));
                sr.transform.localScale = Vector3.one * R(1.1f, 1.7f);
                var cd = sr.gameObject.AddComponent<AquaScape.CloudDrift>();
                cd.velocity = new Vector2(R(0.25f, 0.45f), R(-0.03f, 0.05f));
                cd.parallax = R(0.18f, 0.3f);
                cd.dayAlpha = R(0.22f, 0.38f);
                cd.wrapMinX = -20f;
                cd.wrapMaxX = 100f;
            }
            // cloud shadows
            for (int i = 0; i < 7; i++)
            {
                var sr = SpriteChild(root, "CloudShadow", "FX/cloud_shadow", "Overhead", new Vector3(R(-5, 80), R(0, 34), 0));
                sr.sortingOrder = -10;
                sr.transform.localScale = new Vector3(R(2.5f, 4f), R(1.6f, 2.4f), 1f);
                sr.color = new Color(0.1f, 0.25f, 0.45f, 0.1f);
                var cd = sr.gameObject.AddComponent<AquaScape.CloudDrift>();
                cd.velocity = new Vector2(R(0.3f, 0.45f), 0.02f);
                cd.parallax = 0f;
                cd.dayAlpha = 0.09f;
                cd.wrapMinX = -15f;
                cd.wrapMaxX = 95f;
            }
            // wildlife is placed in build scenery
        }
    }
}
