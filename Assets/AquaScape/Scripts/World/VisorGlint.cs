using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Every few seconds a tiny lens glint flashes on the explorer's helmet,
    /// selling the glossy chrome / glass look.
    /// </summary>
    public class VisorGlint : MonoBehaviour
    {
        public SpriteRenderer glint;
        public SpriteRenderer body;
        public Vector2 interval = new Vector2(2.5f, 5f);
        public float duration = 0.35f;

        float _timer;
        float _t = -1f;

        void Start() => _timer = Random.Range(interval.x, interval.y);

        void Update()
        {
            if (glint == null) return;
            _timer -= Time.deltaTime;
            if (_timer <= 0f)
            {
                _timer = Random.Range(interval.x, interval.y);
                _t = 0f;
                // glint position depends on which way the helmet is facing
                bool side = body != null && body.sprite != null && body.sprite.name.Contains("side");
                bool back = body != null && body.sprite != null && body.sprite.name.Contains("_up_");
                float x = side ? 0.32f : back ? -0.18f : -0.15f;
                if (body != null && body.flipX) x = -x;
                glint.transform.localPosition = new Vector3(x, back ? 1.25f : 1.08f, 0f);
            }

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
