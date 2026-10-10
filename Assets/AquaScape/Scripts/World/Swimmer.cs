using UnityEngine;

namespace AquaScape
{
    // fish in the water or sky fish and butterflies in the air that wander around an area
    public class Swimmer : MonoBehaviour
    {
        public enum Medium { Water, Air }

        public Medium medium = Medium.Water;
        // the area it wanders inside
        public Rect area = new Rect(0, 0, 120, 34);
        public float speed = 1.1f;
        // how fast it turns toward its target
        public float turnRate = 1.5f;
        // animation frames and speed
        public Sprite[] frames;
        public float fps = 6f;
        // how see through it is in the day and at night
        [Range(0f, 1f)] public float dayAlpha = 0.6f;
        [Range(0f, 1f)] public float nightAlpha = 0.25f;

        // the sprite to animate, not the shadow
        public SpriteRenderer body;

        [Header("air only")]
        public float hoverHeight = 2.2f;
        public Transform shadow;

        SpriteRenderer _sr;
        Vector2 _pos, _target, _dir = Vector2.right;
        float _phase;

        void Start()
        {
            _sr = body != null ? body : GetComponentInChildren<SpriteRenderer>();
            _pos = transform.position;
            _phase = Random.value * 10f;
            PickTarget();
        }

        // picks a new random spot to swim to
        void PickTarget()
        {
            var terrain = TerrainPainter.Instance;
            for (int i = 0; i < 12; i++)
            {
                var p = new Vector2(Random.Range(area.xMin, area.xMax), Random.Range(area.yMin, area.yMax));
                // water ones stay over water, air ones can go anywhere
                if (medium == Medium.Air || terrain == null || !terrain.IsWalkable(terrain.WorldToCell(p)))
                {
                    _target = p;
                    return;
                }
            }
        }

        void Update()
        {
            // steer toward the target with a little speed wobble
            float t = Time.time + _phase;
            Vector2 want = (_target - _pos).normalized;
            _dir = Vector3.Slerp(_dir, want, turnRate * Time.deltaTime).normalized;
            float pace = 0.75f + 0.25f * Mathf.Sin(t * 1.3f);
            _pos += _dir * speed * pace * Time.deltaTime;
            if ((_target - _pos).sqrMagnitude < 1f) PickTarget();

            if (medium == Medium.Water)
            {
                // seen from above so rotate to face where its going
                transform.position = _pos;
                float angle = Mathf.Atan2(_dir.y, _dir.x) * Mathf.Rad2Deg + Mathf.Sin(t * 5f) * 5f;
                transform.rotation = Quaternion.Euler(0, 0, angle);
            }
            else
            {
                // seen from the side so flip left or right and bob up and down
                float bob = Mathf.Sin(t * 1.7f) * 0.25f;
                transform.position = _pos;
                _sr.transform.localPosition = new Vector3(0f, hoverHeight + bob, 0f);
                _sr.flipX = _dir.x < 0f;
                if (shadow != null) shadow.localScale = Vector3.one * (0.9f - bob * 0.3f);
            }

            // play the animation
            if (frames != null && frames.Length > 0)
                _sr.sprite = frames[(int)(t * fps) % frames.Length];

            // fade toward night alpha when its dark
            float night = ZoneDirector.Instance != null ? ZoneDirector.Instance.Night : 0f;
            var c = _sr.color;
            c.a = Mathf.Lerp(dayAlpha, nightAlpha, night);
            _sr.color = c;
        }
    }
}
