using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// A fish silhouette gliding under the water surface. It wanders between
    /// random points over open water and slips under islands now and then
    /// (it is drawn below the island tiles, so it disappears beneath them).
    /// </summary>
    public class FishSwimmer : MonoBehaviour
    {
        public Rect area = new Rect(0, 0, 120, 32);
        public float speed = 1.2f;
        public float turnRate = 1.6f;

        Vector2 _target;
        Vector2 _dir = Vector2.right;
        SpriteRenderer _sr;
        float _wiggle;

        void Start()
        {
            _sr = GetComponent<SpriteRenderer>();
            _wiggle = Random.value * 10f;
            PickTarget();
        }

        void PickTarget()
        {
            var terrain = TerrainPainter.Instance;
            for (int i = 0; i < 12; i++)
            {
                var p = new Vector2(Random.Range(area.xMin, area.xMax), Random.Range(area.yMin, area.yMax));
                if (terrain == null || !terrain.IsWalkable(terrain.WorldToCell(p)))
                {
                    _target = p;
                    return;
                }
            }
        }

        void Update()
        {
            Vector2 pos = transform.position;
            Vector2 want = (_target - pos).normalized;
            _dir = Vector3.Slerp(_dir, want, turnRate * Time.deltaTime).normalized;
            float burst = 0.75f + 0.25f * Mathf.Sin(Time.time * 1.3f + _wiggle);
            transform.position = pos + _dir * speed * burst * Time.deltaTime;
            float angle = Mathf.Atan2(_dir.y, _dir.x) * Mathf.Rad2Deg + Mathf.Sin(Time.time * 6f + _wiggle) * 6f;
            transform.rotation = Quaternion.Euler(0, 0, angle);
            if ((_target - pos).sqrMagnitude < 1f) PickTarget();

            // fish are harder to see in the night water
            if (_sr != null && ZoneDirector.Instance != null)
                _sr.color = new Color(1f, 1f, 1f, Mathf.Lerp(0.35f, 0.12f, ZoneDirector.Instance.Night));
        }
    }
}
