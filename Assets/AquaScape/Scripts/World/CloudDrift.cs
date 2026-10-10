using UnityEngine;

namespace AquaScape
{
    // moves clouds or cloud shadows slowly across the level and fades them at night
    public class CloudDrift : MonoBehaviour
    {
        // how fast the cloud drifts
        public Vector2 velocity = new Vector2(0.35f, 0.05f);
        // 0 means fixed in the world, higher means it follows the camera and looks higher up
        public float parallax = 0.25f;
        // the cloud wraps back to min x after passing max x
        public float wrapMinX = -10f, wrapMaxX = 130f;
        // how see through the cloud is during the day
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
            // drift and wrap around
            _worldPos += (Vector3)velocity * Time.deltaTime;
            if (_worldPos.x > wrapMaxX) _worldPos.x = wrapMinX;

            // shift a bit with the camera so it feels higher up
            Vector3 offset = _cam != null ? new Vector3(_cam.position.x, _cam.position.y, 0f) * parallax : Vector3.zero;
            transform.position = _worldPos + offset;

            // fade out as night comes
            if (_sr != null && ZoneDirector.Instance != null)
            {
                var c = _sr.color;
                c.a = dayAlpha * (1f - ZoneDirector.Instance.Night);
                _sr.color = c;
            }
        }
    }
}
