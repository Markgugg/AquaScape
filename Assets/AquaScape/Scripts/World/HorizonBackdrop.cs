using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// A painted far-distance panorama (sky, skyline, moon) along the north
    /// edge of the world. It slides slower than the camera horizontally, so it
    /// reads as very far away.
    /// </summary>
    [DefaultExecutionOrder(100)]   // after the camera has moved this frame
    public class HorizonBackdrop : MonoBehaviour
    {
        [Tooltip("World x the panorama is centred on when the camera is there too.")]
        public float anchorX;
        [Range(0f, 1f)] public float parallax = 0.55f;
        [Tooltip("0 lagoon (always drawn underneath), 1 city, 2 moonpool.")]
        public int zone;

        float _baseY;

        void Start() => _baseY = transform.position.y;

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            float dx = cam.transform.position.x - anchorX;
            transform.position = new Vector3(anchorX + dx * parallax, _baseY, 0f);

            // later zones fade in over the earlier ones as you travel east
            var zd = ZoneDirector.Instance;
            var sr = GetComponent<SpriteRenderer>();
            if (zd == null || sr == null) return;
            float a = zone == 0 ? 1f : zone == 1 ? zd.City * (1f - zd.Night) : zd.Night;
            sr.color = new Color(1f, 1f, 1f, a);
        }
    }
}
