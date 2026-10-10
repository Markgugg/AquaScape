using UnityEngine;

namespace AquaScape
{
    // draws a wavy upside down copy of a tall object on the water under it
    public class WaterReflection : MonoBehaviour
    {
        // the sprite being reflected
        public SpriteRenderer source;
        // how strong the reflection is in the day and at night
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
            // copy the source sprite so animations show up too
            if (source != null && _sr.sprite != source.sprite) _sr.sprite = source.sprite;
            float t = Time.time + _phase;
            // small ripple and stretch so it looks like moving water
            transform.localScale = new Vector3(1f + Mathf.Sin(t * 1.7f) * 0.03f, -(0.9f + Mathf.Sin(t * 1.1f) * 0.03f), 1f);
            transform.localPosition = new Vector3(Mathf.Sin(t * 2.3f) * 0.04f, 0f, 0f);
            float night = ZoneDirector.Instance != null ? ZoneDirector.Instance.Night : 0f;
            _sr.color = new Color(0.75f, 0.95f, 1f, Mathf.Lerp(dayAlpha, nightAlpha, night));
        }
    }
}
