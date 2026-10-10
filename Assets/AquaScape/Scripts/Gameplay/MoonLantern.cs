using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    // a moonpool lantern that lights up when pulsed
    public class MoonLantern : PulseTarget
    {
        public SpriteRenderer sprite;
        public Sprite litSprite;
        public Light2D glow;
        // the group this lantern reports to
        public LanternGroup group;

        public bool IsLit { get; private set; }
        public override bool ShowsPrompt => !IsLit;

        void Update()
        {
            if (glow != null)
                glow.intensity = IsLit ? 1.6f + Mathf.Sin(Time.time * 2f + transform.position.x) * 0.2f : 0f;
        }

        // lights the lantern and tells the group
        public override void OnPulse(Vector2 origin)
        {
            if (IsLit) return;
            IsLit = true;
            sprite.sprite = litSprite;
            int litCount = group != null ? group.LitCount : 1;
            // each lantern rings a step higher in the chord
            AudioManager.Play("lantern_light", 1f + 0.122f * (litCount - 1), 1f, transform.position);
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.sparkleFx : null, transform.position + Vector3.up * 1.5f,
                new Color(0.8f, 0.75f, 1f));
            group?.OnLanternLit();
        }
    }
}
