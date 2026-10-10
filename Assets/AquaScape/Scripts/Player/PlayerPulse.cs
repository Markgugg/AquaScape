using System.Collections;
using UnityEngine;

namespace AquaScape
{
    // sends out a pulse ring that every pulse target in range reacts to
    // also shows a space prompt over the closest thing worth pulsing
    public class PlayerPulse : MonoBehaviour
    {
        // how far the pulse reaches
        public float radius = 2.4f;
        // wait time between pulses
        public float cooldown = 0.5f;

        [Header("visuals")]
        public SpriteRenderer ring;
        public ParticleSystem burst;
        public SpriteRenderer prompt;

        // how many times the player has pulsed
        public int PulseCount { get; private set; }

        float _cooldownTimer;
        float _promptAlpha;
        PulseTarget _promptTarget;

        void Start()
        {
            if (ring != null) ring.enabled = false;
            if (prompt != null) prompt.color = new Color(1, 1, 1, 0);
        }

        // fires a pulse if the cooldown is done, returns true if it worked
        public bool TryPulse()
        {
            if (_cooldownTimer > 0f) return false;
            _cooldownTimer = cooldown;
            PulseCount++;

            Vector2 origin = transform.position;
            AudioManager.Play("pulse", Random.Range(0.97f, 1.03f), 1f, origin);
            CameraFollow.Shake(0.06f, 0.15f);
            if (burst != null) burst.Emit(24);
            if (ring != null) StartCoroutine(RingRoutine());
            GetComponent<PlayerController>()?.Squash(new Vector3(1.15f, 0.88f, 1f));

            // copy the list since reacting can disable or destroy targets
            foreach (var target in PulseTarget.All.ToArray())
            {
                if (target == null || !target.isActiveAndEnabled) continue;
                float d = Vector2.Distance(origin, target.transform.position);
                if (d <= radius + target.reachBonus)
                    target.OnPulse(origin);
            }
            return true;
        }

        // grows and fades the ring sprite
        IEnumerator RingRoutine()
        {
            ring.enabled = true;
            float t = 0f;
            const float duration = 0.45f;
            while (t < duration)
            {
                t += Time.deltaTime;
                float k = t / duration;
                float ease = 1f - (1f - k) * (1f - k) * (1f - k);
                // ring sprite is 2 units wide at scale 1
                ring.transform.localScale = Vector3.one * (radius * ease);
                ring.color = new Color(0.7f, 0.98f, 1f, (1f - k) * 0.9f);
                yield return null;
            }
            ring.enabled = false;
        }

        void Update()
        {
            _cooldownTimer -= Time.deltaTime;
            UpdatePrompt();
        }

        // shows a floating key prompt above the closest thing you can pulse
        void UpdatePrompt()
        {
            if (prompt == null) return;
            bool playing = GameManager.Instance == null || GameManager.Instance.IsPlaying;

            PulseTarget best = null;
            float bestD = radius;
            if (playing)
            {
                foreach (var t in PulseTarget.All)
                {
                    if (t == null || !t.isActiveAndEnabled || !t.ShowsPrompt) continue;
                    float d = Vector2.Distance(transform.position, t.transform.position);
                    if (d < bestD) { bestD = d; best = t; }
                }
            }
            if (best != null) _promptTarget = best;

            _promptAlpha = Mathf.MoveTowards(_promptAlpha, best != null ? 1f : 0f, Time.deltaTime * 6f);
            prompt.color = new Color(1, 1, 1, _promptAlpha);
            if (_promptTarget != null)
            {
                float bob = Mathf.Sin(Time.time * 4f) * 0.06f;
                prompt.transform.position = _promptTarget.transform.position + _promptTarget.promptOffset + Vector3.up * bob;
            }
        }
    }
}
