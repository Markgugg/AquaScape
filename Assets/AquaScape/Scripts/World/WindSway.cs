using UnityEngine;

namespace AquaScape
{
    /// <summary>Slow wind sway for palms and plants, rotating around the base pivot.</summary>
    public class WindSway : MonoBehaviour
    {
        public float degrees = 1.6f;
        public float speed = 0.9f;
        float _phase;

        void Start() => _phase = transform.position.x * 0.35f + transform.position.y * 0.2f;

        void Update()
        {
            float t = Time.time * speed + _phase;
            // two layered sines so neighbouring palms never move in lockstep
            float a = Mathf.Sin(t) * degrees + Mathf.Sin(t * 2.3f + 1f) * degrees * 0.3f;
            transform.localRotation = Quaternion.Euler(0f, 0f, a);
        }
    }
}
