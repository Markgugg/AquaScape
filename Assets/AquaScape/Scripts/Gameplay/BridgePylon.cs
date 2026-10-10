using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    /// <summary>A crystal pylon that raises a glass bridge when pulsed.</summary>
    public class BridgePylon : PulseTarget
    {
        public SpriteRenderer sprite;
        public Sprite onSprite;
        public Light2D glow;
        public BridgeBuilder bridge;

        bool _active;

        public override bool ShowsPrompt => !_active;

        void Update()
        {
            if (glow != null)
                glow.intensity = _active ? 0.8f + Mathf.Sin(Time.time * 3f) * 0.1f : 0.2f;
        }

        public override void OnPulse(Vector2 origin)
        {
            if (_active) return;
            _active = true;
            sprite.sprite = onSprite;
            AudioManager.Play("pylon_activate", 1f, 1f, transform.position);
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.sparkleFx : null, transform.position + Vector3.up * 1.2f);
            if (bridge != null) bridge.Activate();
        }
    }
}
