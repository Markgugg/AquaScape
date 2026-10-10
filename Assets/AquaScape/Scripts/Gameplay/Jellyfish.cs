using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    /// <summary>
    /// A drifting Moonpool jellyfish. It glides around a loop near its spawn
    /// point; touching it bumps the player back and knocks a few bubbles loose
    /// (they can be picked up again). A pulse gently repels and calms it for a
    /// moment, which is how you get past them. Dashing through is also safe.
    /// </summary>
    public class Jellyfish : PulseTarget
    {
        [Header("Patrol loop")]
        public Vector2 radius = new Vector2(2f, 1.2f);
        public float speed = 0.45f;
        public bool clockwise;

        [Header("Contact")]
        public float touchRadius = 0.55f;
        public int bubblesKnockedOut = 3;
        public float bumpForce = 7f;

        [Header("Visuals")]
        public SpriteRenderer sprite;
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

            // patrol around the loop, slowing right down while calmed
            float pace = _calmTimer > 0f ? 0.15f : 1f;
            _angle += (clockwise ? -1f : 1f) * speed * pace * dt;
            _repel = Vector3.Lerp(_repel, Vector3.zero, dt * 0.8f);
            Vector3 loop = new Vector3(Mathf.Cos(_angle) * radius.x, Mathf.Sin(_angle) * radius.y, 0f);
            transform.position = _center + loop + _repel;

            // animation: flipbook + float bob; dim while calmed
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
                    Bubble.Spawn(player.transform.position, to, 0.5f);   // never expire: a full 100% run stays possible
                }
            }
            _calmTimer = 1.2f;   // don't double-hit
        }

        public override void OnPulse(Vector2 origin)
        {
            Vector3 away = ((Vector2)transform.position - origin).normalized;
            _repel += away * 1.4f;
            _calmTimer = 2.5f;
            AudioManager.Play("jelly_repel", Random.Range(0.9f, 1.1f), 1f, transform.position);
        }
    }
}
