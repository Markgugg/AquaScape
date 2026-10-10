using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    // a jellyfish that floats in a loop and knocks bubbles out of the player on touch
    // pulsing it pushes it away and calms it for a bit, dashing through is safe too
    public class Jellyfish : PulseTarget
    {
        // size and speed of the loop it swims in
        [Header("patrol loop")]
        public Vector2 radius = new Vector2(2f, 1.2f);
        public float speed = 0.45f;
        public bool clockwise;

        // what happens when it touches the player
        [Header("contact")]
        public float touchRadius = 0.55f;
        public int bubblesKnockedOut = 3;
        public float bumpForce = 7f;

        [Header("visuals")]
        public SpriteRenderer sprite;
        // animation frames
        public Sprite[] frames;
        public float fps = 6f;
        public Light2D glow;
        public Transform shadow;

        Vector3 _center;
        float _angle;
        float _calmTimer;
        Vector3 _repel;

        public override bool ShowsPrompt => false;

        void Start()
        {
            _center = transform.position;
            _angle = Random.value * Mathf.PI * 2f;
            reachBonus = 0.4f;
        }

        void Update()
        {
            float dt = Time.deltaTime;
            _calmTimer -= dt;

            // move around the loop, slowing way down while calm
            float pace = _calmTimer > 0f ? 0.15f : 1f;
            _angle += (clockwise ? -1f : 1f) * speed * pace * dt;
            _repel = Vector3.Lerp(_repel, Vector3.zero, dt * 0.8f);
            Vector3 loop = new Vector3(Mathf.Cos(_angle) * radius.x, Mathf.Sin(_angle) * radius.y, 0f);
            transform.position = _center + loop + _repel;

            // flip through frames, bob up and down and dim while calm
            if (frames != null && frames.Length > 0)
                sprite.sprite = frames[(int)(Time.time * fps + _center.x) % frames.Length];
            float bob = Mathf.Sin(Time.time * 2f + _center.x) * 0.12f;
            sprite.transform.localPosition = new Vector3(0f, 0.9f + bob, 0f);
            if (shadow != null) shadow.localScale = Vector3.one * (1f - bob * 0.8f);
            float calm = Mathf.Clamp01(_calmTimer);
            sprite.color = Color.Lerp(Color.white, new Color(0.7f, 0.75f, 1f, 0.55f), calm);
            if (glow != null) glow.intensity = Mathf.Lerp(0.9f, 0.3f, calm) + Mathf.Sin(Time.time * 3f) * 0.1f;

            CheckTouch();
        }

        // bumps the player and drops some of their bubbles if they touch
        void CheckTouch()
        {
            var player = PlayerController.Instance;
            if (player == null || _calmTimer > 0f || player.IsInvulnerable) return;
            if (GameManager.Instance != null && !GameManager.Instance.IsPlaying) return;
            if (Vector2.Distance(player.transform.position, transform.position) > touchRadius) return;

            player.Bump(transform.position, bumpForce);
            AudioManager.Play("jelly_hit", 1f, 1f, transform.position);
            int lost = GameManager.Instance != null ? GameManager.Instance.LoseBubbles(bubblesKnockedOut) : 0;
            if (lost > 0)
            {
                AudioManager.Play("bubble_drop", 1f, 1f, player.transform.position);
                for (int i = 0; i < lost; i++)
                {
                    Vector2 r = Random.insideUnitCircle.normalized * Random.Range(1.2f, 2f);
                    Vector3 to = player.transform.position + (Vector3)r;
                    var terrain = TerrainPainter.Instance;
                    if (terrain != null && !terrain.IsWalkable(terrain.WorldToCell(to)))
                        to = player.transform.position - (Vector3)r * 0.5f;
                    // these never expire so you can still get every bubble
                    Bubble.Spawn(player.transform.position, to, 0.5f);
                }
            }
            // stops it from hitting twice in a row
            _calmTimer = 1.2f;
        }

        // pushes the jellyfish away and calms it down
        public override void OnPulse(Vector2 origin)
        {
            Vector3 away = ((Vector2)transform.position - origin).normalized;
            _repel += away * 1.4f;
            _calmTimer = 2.5f;
            AudioManager.Play("jelly_repel", Random.Range(0.9f, 1.1f), 1f, transform.position);
        }
    }
}
