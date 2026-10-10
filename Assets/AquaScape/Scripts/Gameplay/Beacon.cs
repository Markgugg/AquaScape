using System.Collections;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    /// <summary>
    /// The Aqua Beacon of an area. Pulse it while carrying that area's Prism
    /// Shard to light it: the orb blazes up, a new music layer joins, and the
    /// way forward opens (a bridge, or the Moonpool portal for the last one).
    /// </summary>
    public class Beacon : PulseTarget
    {
        public int zone;
        public SpriteRenderer sprite;
        public Sprite litSprite;
        public Light2D glow;
        public ParticleSystem sparkles;
        public float litIntensity = 2.4f;

        [Header("Unlocks")]
        public BridgeBuilder unlocksBridge;
        public MoonpoolPortal unlocksPortal;

        public bool IsLit { get; private set; }
        float _deniedTimer;

        public override bool ShowsPrompt => !IsLit;

        void Update()
        {
            // unlit beacons breathe softly so they read as "important but asleep"
            if (!IsLit && glow != null)
                glow.intensity = 0.35f + Mathf.Sin(Time.time * 1.6f) * 0.12f;

            // little shake after a denied pulse
            if (_deniedTimer > 0f)
            {
                _deniedTimer -= Time.deltaTime;
                sprite.transform.localPosition = new Vector3(Mathf.Sin(_deniedTimer * 60f) * 0.04f * _deniedTimer * 3f, 0f, 0f);
            }
        }

        public override void OnPulse(Vector2 origin)
        {
            if (IsLit) return;
            var gm = GameManager.Instance;
            if (gm != null && !gm.HasShard(zone))
            {
                _deniedTimer = 0.35f;
                AudioManager.Play("beacon_denied", 1f, 1f, transform.position);
                UIManager.Toast("The Beacon is dark", "It needs this area's Prism Shard");
                return;
            }
            StartCoroutine(LightRoutine());
        }

        IEnumerator LightRoutine()
        {
            IsLit = true;
            AudioManager.Play("beacon_light", 1f, 1f, transform.position);
            CameraFollow.Shake(0.12f, 0.5f);
            if (sparkles != null) sparkles.Play();

            float t = 0f;
            const float rise = 1.1f;
            bool swapped = false;
            while (t < rise)
            {
                t += Time.deltaTime;
                float k = t / rise;
                if (!swapped && k > 0.25f)
                {
                    sprite.sprite = litSprite;
                    swapped = true;
                    GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.sparkleFx : null, transform.position + Vector3.up * 2.4f);
                }
                if (glow != null) glow.intensity = Mathf.Lerp(0.4f, litIntensity * 1.6f, Mathf.Sin(k * Mathf.PI * 0.5f));
                yield return null;
            }
            // settle down from the flash to the steady glow
            t = 0f;
            while (t < 0.6f)
            {
                t += Time.deltaTime;
                if (glow != null) glow.intensity = Mathf.Lerp(litIntensity * 1.6f, litIntensity, t / 0.6f);
                yield return null;
            }

            GameManager.Instance?.NotifyBeaconLit(zone);
            UIManager.Toast("Beacon lit!", unlocksPortal != null ? "The Moonpool awakens..." : "A glass bridge is forming...");

            if (unlocksBridge != null) unlocksBridge.Activate(0.3f);
            if (unlocksPortal != null) unlocksPortal.Activate();
        }
    }
}
