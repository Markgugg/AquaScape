using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Small looping motions for setpieces: fake a 3D spin by scaling x
    /// (floating chrome rings), rotate (turbine blades), or flip through
    /// frames (waterfalls).
    /// </summary>
    public class SpinFake3D : MonoBehaviour
    {
        public enum Mode { ScaleSpin, Rotate, Flipbook }

        public Mode mode = Mode.ScaleSpin;
        public float speed = 0.6f;
        public Sprite[] frames;
        float _phase;
        SpriteRenderer _sr;
        Vector3 _scale;

        void Start()
        {
            _sr = GetComponent<SpriteRenderer>();
            _scale = transform.localScale;
            _phase = Random.value * 10f;
        }

        void Update()
        {
            float t = Time.time + _phase;
            switch (mode)
            {
                case Mode.ScaleSpin:
                    float s = Mathf.Cos(t * speed);
                    transform.localScale = new Vector3(_scale.x * (0.15f + 0.85f * Mathf.Abs(s)), _scale.y, _scale.z);
                    break;
                case Mode.Rotate:
                    transform.Rotate(0f, 0f, -speed * 60f * Time.deltaTime);
                    break;
                case Mode.Flipbook:
                    if (_sr != null && frames != null && frames.Length > 0)
                        _sr.sprite = frames[(int)(t * speed) % frames.Length];
                    break;
            }
        }
    }
}
