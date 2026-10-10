using System.Collections;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    // the beacon of an area, pulse it while holding that area shard to light it
    // lighting it opens a bridge or the moonpool portal for the last one
    public class Beacon : PulseTarget
    {
        // which area this beacon belongs to
        public int zone;
        public SpriteRenderer sprite;
        public Sprite litSprite;
        public Light2D glow;
        public ParticleSystem sparkles;
        // glow strength once lit
        public float litIntensity = 2.4f;

        // what lighting this beacon opens up
        [Header("unlocks")]
        public BridgeBuilder unlocksBridge;
        public MoonpoolPortal unlocksPortal;

        public bool IsLit { get; private set; }
        float _deniedTimer;

        public override bool ShowsPrompt => !IsLit;

        void Update()
        {
            // unlit beacons glow softly so they look important but asleep
            if (!IsLit && glow != null)
                glow.intensity = 0.35f + Mathf.Sin(Time.time * 1.6f) * 0.12f;

            // little shake after a denied pulse
            if (_deniedTimer > 0f)
            {
                _deniedTimer -= Time.deltaTime;
                sprite.transform.localPosition = new Vector3(Mathf.Sin(_deniedTimer * 60f) * 0.04f * _deniedTimer * 3f, 0f, 0f);
            }
        }

        // lights the beacon if the player has the shard, otherwise shakes
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

        // flashes the beacon on and then unlocks the next thing
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
