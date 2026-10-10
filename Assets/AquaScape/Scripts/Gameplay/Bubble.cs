using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Collectible bubble. Bobs gently in place, is pulled toward the player
    /// once they get close (a little magnet so collecting feels generous) and
    /// pops with a note that climbs the scale during quick combos.
    ///
    /// Bubbles can also be "launched" (out of a clam, or knocked out of the
    /// player by a jellyfish): they fly along an arc first and can only be
    /// collected once they land. Dropped bubbles fade away if left too long.
    /// </summary>
    public class Bubble : MonoBehaviour
    {
        public float magnetRadius = 1.8f;
        public float collectRadius = 0.45f;
        public float bobHeight = 0.08f;
        public Transform visual;
        public SpriteRenderer sprite;

        [Tooltip("Seconds before a dropped bubble disappears (0 = never).")]
        public float lifetime = 0f;

        float _phase;
        float _age;
        Vector3 _flyFrom, _flyTo;
        float _flyTime, _flyDuration;
        float _magnetSpeed;
        bool _collected;

        void Awake()
        {
            _phase = Random.value * 10f;
        }

        /// <summary>Throw the bubble from `from` to `to` along a hop.</summary>
        public void Launch(Vector3 from, Vector3 to, float duration, float lifetimeSeconds = 0f)
        {
            _flyFrom = from;
            _flyTo = to;
            _flyTime = 0f;
            _flyDuration = duration;
            lifetime = lifetimeSeconds;
            transform.position = from;
        }

        bool Flying => _flyTime < _flyDuration;

        void Update()
        {
            _age += Time.deltaTime;
            float bob = Mathf.Sin((Time.time + _phase) * 2.2f) * bobHeight;

            if (Flying)
            {
                _flyTime += Time.deltaTime;
                float k = Mathf.Clamp01(_flyTime / _flyDuration);
                transform.position = Vector3.Lerp(_flyFrom, _flyTo, 1f - (1f - k) * (1f - k));
                bob += Mathf.Sin(k * Mathf.PI) * 0.9f;   // hop arc
            }
            if (visual != null) visual.localPosition = new Vector3(0f, 0.35f + bob, 0f);

            if (lifetime > 0f)
            {
                float left = lifetime - _age;
                if (sprite != null && left < 2f)
                    sprite.enabled = Mathf.Repeat(left * 8f, 1f) > 0.35f;
                if (left <= 0f) { Destroy(gameObject); return; }
            }

            if (!Flying) UpdateMagnet();
        }

        void UpdateMagnet()
        {
            var player = PlayerController.Instance;
            if (player == null || _collected) return;
            if (GameManager.Instance != null && !GameManager.Instance.IsPlaying) return;

            Vector3 target = player.transform.position + Vector3.up * 0.35f;
            float d = Vector2.Distance(transform.position + Vector3.up * 0.35f, target);
            if (d < collectRadius) { Collect(); return; }
            if (d < magnetRadius)
            {
                _magnetSpeed += Time.deltaTime * 28f;
                transform.position = Vector3.MoveTowards(transform.position, player.transform.position, _magnetSpeed * Time.deltaTime);
            }
            else _magnetSpeed = 0f;
        }

        void Collect()
        {
            _collected = true;
            GameManager.Instance?.AddBubbles(1);
            AudioManager.PlayBubbleNote(transform.position);
            if (GameAssets.Instance != null)
                GameAssets.Burst(GameAssets.Instance.popFx, transform.position + Vector3.up * 0.4f);
            Destroy(gameObject);
        }

        /// <summary>Spawn a bubble that hops from `from` to `to`.</summary>
        public static Bubble Spawn(Vector3 from, Vector3 to, float flight, float lifetimeSeconds = 0f)
        {
            var prefab = GameAssets.Instance != null ? GameAssets.Instance.bubblePrefab : null;
            if (prefab == null) return null;
            var b = Instantiate(prefab, from, Quaternion.identity);
            b.Launch(from, to, flight, lifetimeSeconds);
            return b;
        }
    }
}
