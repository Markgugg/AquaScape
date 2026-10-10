using System;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    /// <summary>
    /// The level runs west to east through three areas that share one scene:
    /// Blue Lagoon (day) -> Glass City (bright afternoon) -> Moonpool (night).
    /// This component turns the camera's x position into a smooth 0..2 "zone
    /// blend" and drives the global light, shader globals (water colours) and
    /// ambient particles from it, so the world changes gradually as you walk.
    /// </summary>
    public class ZoneDirector : MonoBehaviour
    {
        [Serializable]
        public class ZoneLook
        {
            public string title = "Blue Lagoon";
            public string subtitle = "Bright & peaceful";
            public Color lightColor = Color.white;
            public float lightIntensity = 1f;
        }

        public static ZoneDirector Instance { get; private set; }

        [Tooltip("World x range over which Lagoon fades into Glass City.")]
        public Vector2 lagoonToCity = new Vector2(36f, 44f);
        [Tooltip("World x range over which Glass City fades into the Moonpool night.")]
        public Vector2 cityToMoon = new Vector2(76f, 86f);

        public ZoneLook[] zones = new ZoneLook[GameManager.ZoneCount];
        public Light2D globalLight;

        [Header("Ambient particles (follow the camera)")]
        public ParticleSystem dayMotes;
        public ParticleSystem nightFireflies;
        public float dayMoteRate = 6f;
        public float fireflyRate = 10f;

        [Header("Lights that only shine at night (e.g. the helmet lamp)")]
        public Light2D[] nightLights;
        float[] _nightLightBase;

        /// <summary>0 = lagoon, 1 = city, 2 = moonpool (fractional in between).</summary>
        public float Blend { get; private set; }
        /// <summary>0..1 how much of the city look is applied.</summary>
        public float City => Mathf.Clamp01(Blend);
        /// <summary>0..1 how dark / night-time the world currently is.</summary>
        public float Night => Mathf.Clamp01(Blend - 1f);
        public int PlayerZone { get; private set; } = -1;

        public event Action<int> ZoneEntered;

        static readonly int ZoneEdgesId = Shader.PropertyToID("_AquaZoneEdges");
        static readonly int NightId = Shader.PropertyToID("_AquaNight");

        void Awake()
        {
            Instance = this;
            PushShaderGlobals();
        }

        public float BlendAt(float x)
        {
            float a = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(lagoonToCity.x, lagoonToCity.y, x));
            float b = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(cityToMoon.x, cityToMoon.y, x));
            return a + b;
        }

        public int ZoneAt(float x)
        {
            if (x < (lagoonToCity.x + lagoonToCity.y) * 0.5f) return 0;
            if (x < (cityToMoon.x + cityToMoon.y) * 0.5f) return 1;
            return 2;
        }

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            Blend = BlendAt(cam.transform.position.x);
            PushShaderGlobals();

            // Global light: interpolate between the neighbouring zone looks.
            if (globalLight != null && zones.Length == 3)
            {
                int i = Mathf.Min(Mathf.FloorToInt(Blend), 1);
                float t = Blend - i;
                globalLight.color = Color.Lerp(zones[i].lightColor, zones[i + 1].lightColor, t);
                globalLight.intensity = Mathf.Lerp(zones[i].lightIntensity, zones[i + 1].lightIntensity, t);
            }

            if (nightLights != null)
            {
                _nightLightBase ??= System.Array.ConvertAll(nightLights, l => l != null ? l.intensity : 0f);
                for (int k = 0; k < nightLights.Length; k++)
                    if (nightLights[k] != null) nightLights[k].intensity = _nightLightBase[k] * (0.15f + 0.85f * Night);
            }

            SetRate(dayMotes, dayMoteRate * (1f - Night));
            SetRate(nightFireflies, fireflyRate * Night);

            // Announce a new area once the player crosses its midpoint.
            var player = PlayerController.Instance;
            if (player != null && GameManager.Instance != null && GameManager.Instance.IsPlaying)
            {
                int z = ZoneAt(player.transform.position.x);
                if (z != PlayerZone)
                {
                    bool first = PlayerZone < 0;
                    PlayerZone = z;
                    if (!first) AudioManager.Play("zone_enter");
                    ZoneEntered?.Invoke(z);
                }
            }
        }

        void PushShaderGlobals()
        {
            Shader.SetGlobalVector(ZoneEdgesId, new Vector4(lagoonToCity.x, lagoonToCity.y, cityToMoon.x, cityToMoon.y));
            Shader.SetGlobalFloat(NightId, Night);
        }

        static void SetRate(ParticleSystem ps, float rate)
        {
            if (ps == null) return;
            var em = ps.emission;
            em.rateOverTime = rate;
        }
    }
}
