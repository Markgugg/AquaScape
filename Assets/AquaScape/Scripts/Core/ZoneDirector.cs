using System;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    // blends the lagoon, city and moonpool looks based on the camera x position
    // and drives the light, water colors and ambient particles from it
    public class ZoneDirector : MonoBehaviour
    {
        // the name and lighting for one zone
        [Serializable]
        public class ZoneLook
        {
            public string title = "Blue Lagoon";
            public string subtitle = "Bright & peaceful";
            public Color lightColor = Color.white;
            public float lightIntensity = 1f;
        }

        public static ZoneDirector Instance { get; private set; }

        // x range where the lagoon fades into the city
        public Vector2 lagoonToCity = new Vector2(36f, 44f);
        // x range where the city fades into the moonpool night
        public Vector2 cityToMoon = new Vector2(76f, 86f);

        // one look per zone
        public ZoneLook[] zones = new ZoneLook[GameManager.ZoneCount];
        public Light2D globalLight;

        [Header("ambient particles")]
        public ParticleSystem dayMotes;
        public ParticleSystem nightFireflies;
        public float dayMoteRate = 6f;
        public float fireflyRate = 10f;

        [Header("night only lights")]
        // lights like the helmet lamp that get brighter at night
        public Light2D[] nightLights;
        float[] _nightLightBase;

        // 0 is lagoon, 1 is city, 2 is moonpool, with fractions in between
        public float Blend { get; private set; }
        // 0 to 1 how much city look is applied
        public float City => Mathf.Clamp01(Blend);
        // 0 to 1 how dark the world is right now
        public float Night => Mathf.Clamp01(Blend - 1f);
        public int PlayerZone { get; private set; } = -1;

        // fires when the player walks into a new zone
        public event Action<int> ZoneEntered;

        void Awake()
        {
            Instance = this;
            PushShaderGlobals();
        }

        void Start()
        {
            // remember how bright each night light is so we can scale it later
            if (nightLights == null) return;
            _nightLightBase = new float[nightLights.Length];
            for (int k = 0; k < nightLights.Length; k++)
                if (nightLights[k] != null) _nightLightBase[k] = nightLights[k].intensity;
        }

        // gets the zone blend value for an x position
        public float BlendAt(float x)
        {
            float a = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(lagoonToCity.x, lagoonToCity.y, x));
            float b = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(cityToMoon.x, cityToMoon.y, x));
            return a + b;
        }

        // gets which zone an x position is in
        public int ZoneAt(float x)
        {
            if (x < (lagoonToCity.x + lagoonToCity.y) * 0.5f) return 0;
            if (x < (cityToMoon.x + cityToMoon.y) * 0.5f) return 1;
            return 2;
        }

        // updates the light, shaders and particles every frame
        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            Blend = BlendAt(cam.transform.position.x);
            PushShaderGlobals();

            // lerp the global light between the two nearest zones
            if (globalLight != null && zones.Length == 3)
            {
                int i = Mathf.Min(Mathf.FloorToInt(Blend), 1);
                float t = Blend - i;
                globalLight.color = Color.Lerp(zones[i].lightColor, zones[i + 1].lightColor, t);
                globalLight.intensity = Mathf.Lerp(zones[i].lightIntensity, zones[i + 1].lightIntensity, t);
            }

            // night lights stay dim in the day and get bright at night
            if (nightLights != null && _nightLightBase != null)
            {
                for (int k = 0; k < nightLights.Length; k++)
                    if (nightLights[k] != null) nightLights[k].intensity = _nightLightBase[k] * (0.15f + 0.85f * Night);
            }

            // swap day motes for fireflies as night comes in
            SetRate(dayMotes, dayMoteRate * (1f - Night));
            SetRate(nightFireflies, fireflyRate * Night);

            // announce a new zone once the player crosses its middle
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

        // sends the zone edges and night value to the shaders
        void PushShaderGlobals()
        {
            Shader.SetGlobalVector("_AquaZoneEdges", new Vector4(lagoonToCity.x, lagoonToCity.y, cityToMoon.x, cityToMoon.y));
            Shader.SetGlobalFloat("_AquaNight", Night);
        }

        // sets how many particles a system spawns per second
        static void SetRate(ParticleSystem ps, float rate)
        {
            if (ps == null) return;
            var em = ps.emission;
            em.rateOverTime = rate;
        }
    }
}
