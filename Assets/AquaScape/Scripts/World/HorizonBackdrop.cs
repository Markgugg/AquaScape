using UnityEngine;

namespace AquaScape
{
    // far away background picture along the top of the world that scrolls slower than the camera
    [DefaultExecutionOrder(100)]   // runs after the camera moves
    public class HorizonBackdrop : MonoBehaviour
    {
        // world x where the picture is centered
        public float anchorX;
        // how much it moves with the camera
        [Range(0f, 1f)] public float parallax = 0.55f;
        // 0 is lagoon and always shows, 1 is city, 2 is moonpool
        public int zone;

        float _baseY;

        void Start() => _baseY = transform.position.y;

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            float dx = cam.transform.position.x - anchorX;
            transform.position = new Vector3(anchorX + dx * parallax, _baseY, 0f);

            // later zones fade in over the earlier ones as you go east
            var zd = ZoneDirector.Instance;
            var sr = GetComponent<SpriteRenderer>();
            if (zd == null || sr == null) return;
            float a = zone == 0 ? 1f : zone == 1 ? zd.City * (1f - zd.Night) : zd.Night;
            sr.color = new Color(1f, 1f, 1f, a);
        }
    }
}
