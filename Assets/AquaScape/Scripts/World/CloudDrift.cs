using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Big soft clouds (or their shadows) drifting slowly across the level.
    /// Clouds sit "above" the world, so they are offset by a parallax factor
    /// relative to the camera, and fade out as night falls.
    /// </summary>
    public class CloudDrift : MonoBehaviour
    {
        public Vector2 velocity = new Vector2(0.35f, 0.05f);
        [Tooltip("0 = fixed in the world, >0 = moves with the camera (appears higher up).")]
        public float parallax = 0.25f;
        public float wrapMinX = -10f, wrapMaxX = 130f;
        [Range(0f, 1f)] public float dayAlpha = 0.55f;

        SpriteRenderer _sr;
        Vector3 _worldPos;
        Transform _cam;

        void Start()
        {
            _sr = GetComponent<SpriteRenderer>();
            _worldPos = transform.position;
            if (Camera.main != null) _cam = Camera.main.transform;
        }

        void LateUpdate()
        {
            _worldPos += (Vector3)velocity * Time.deltaTime;
            if (_worldPos.x > wrapMaxX) _worldPos.x = wrapMinX;

            Vector3 offset = _cam != null ? new Vector3(_cam.position.x, _cam.position.y, 0f) * parallax : Vector3.zero;
            transform.position = _worldPos + offset;

            if (_sr != null && ZoneDirector.Instance != null)
            {
                var c = _sr.color;
                c.a = dayAlpha * (1f - ZoneDirector.Instance.Night);
                _sr.color = c;
            }
        }
    }
}
