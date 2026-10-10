using UnityEngine;

namespace AquaScape
{
    // slowly sways palms and plants in the wind
    public class WindSway : MonoBehaviour
    {
        // how far it leans and how fast
        public float degrees = 1.6f;
        public float speed = 0.9f;
        float _phase;

        void Start() => _phase = transform.position.x * 0.35f + transform.position.y * 0.2f;

        void Update()
        {
            float t = Time.time * speed + _phase;
            // two sine waves mixed so plants next to each other dont move the same
            float a = Mathf.Sin(t) * degrees + Mathf.Sin(t * 2.3f + 1f) * degrees * 0.3f;
            transform.localRotation = Quaternion.Euler(0f, 0f, a);
        }
    }
}
