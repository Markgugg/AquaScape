using UnityEngine;

namespace AquaScape
{
    // flashes a small shine on the explorers helmet every few seconds
    public class VisorGlint : MonoBehaviour
    {
        // the shine sprite and the player body sprite
        public SpriteRenderer glint;
        public SpriteRenderer body;
        // min and max seconds between flashes
        public Vector2 interval = new Vector2(2.5f, 5f);
        // how long one flash lasts
        public float duration = 0.35f;

        float _timer;
        float _t = -1f;

        void Start() => _timer = Random.Range(interval.x, interval.y);

        void Update()
        {
            if (glint == null) return;

            // count down to the next flash
            _timer -= Time.deltaTime;
            if (_timer <= 0f)
            {
                _timer = Random.Range(interval.x, interval.y);
                _t = 0f;
                // move the shine based on which way the helmet faces
                bool side = body != null && body.sprite != null && body.sprite.name.Contains("side");
                bool back = body != null && body.sprite != null && body.sprite.name.Contains("_up_");
                float x = side ? 0.32f : back ? -0.18f : -0.15f;
                if (body != null && body.flipX) x = -x;
                glint.transform.localPosition = new Vector3(x, back ? 1.25f : 1.08f, 0f);
            }

            // play the flash, it fades in and out and spins a bit
            if (_t >= 0f)
            {
                _t += Time.deltaTime;
                float k = _t / duration;
                float a = Mathf.Sin(Mathf.Clamp01(k) * Mathf.PI);
                glint.color = new Color(1f, 1f, 1f, a);
                glint.transform.localScale = Vector3.one * (0.4f + a * 0.6f);
                glint.transform.localRotation = Quaternion.Euler(0, 0, k * 90f);
                if (k >= 1f) _t = -1f;
            }
            else glint.color = new Color(1f, 1f, 1f, 0f);
        }
    }
}
