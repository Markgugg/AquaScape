using UnityEngine;

namespace AquaScape
{
    // makes props like shards or flowers float up and down
    public class Bobbing : MonoBehaviour
    {
        // how far it moves up and down
        public float amplitude = 0.06f;
        // how fast it bobs
        public float frequency = 1.5f;
        Vector3 _base;
        float _phase;

        void Start()
        {
            // random phase so props dont all bob together
            _base = transform.localPosition;
            _phase = Random.value * 10f;
        }

        void Update()
        {
            transform.localPosition = _base + Vector3.up * Mathf.Sin((Time.time + _phase) * frequency) * amplitude;
        }
    }
}
