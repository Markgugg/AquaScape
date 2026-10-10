using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// A soft, rippling mirror image of a tall object drawn on the water layer
    /// beneath it. Because islands are drawn above the water, reflections only
    /// show where the object stands near open water - which is exactly where a
    /// real reflection would be visible.
    /// </summary>
    public class WaterReflection : MonoBehaviour
    {
        public SpriteRenderer source;
        [Range(0f, 1f)] public float dayAlpha = 0.28f;
        [Range(0f, 1f)] public float nightAlpha = 0.4f;

        SpriteRenderer _sr;
        float _phase;

        void Start()
        {
            _sr = GetComponent<SpriteRenderer>();
            _phase = transform.position.x * 0.7f;
        }

        void LateUpdate()
        {
            if (source != null && _sr.sprite != source.sprite) _sr.sprite = source.sprite;
            float t = Time.time + _phase;
            // gentle horizontal ripple + slight stretch, like a moving surface
            transform.localScale = new Vector3(1f + Mathf.Sin(t * 1.7f) * 0.03f, -(0.9f + Mathf.Sin(t * 1.1f) * 0.03f), 1f);
            transform.localPosition = new Vector3(Mathf.Sin(t * 2.3f) * 0.04f, 0f, 0f);
            float night = ZoneDirector.Instance != null ? ZoneDirector.Instance.Night : 0f;
            _sr.color = new Color(0.75f, 0.95f, 1f, Mathf.Lerp(dayAlpha, nightAlpha, night));
        }
    }
}
