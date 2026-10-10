using UnityEngine;

namespace AquaScape
{
    /// <summary>Gentle up/down float for props such as shards or glowing flowers.</summary>
    public class Bobbing : MonoBehaviour
    {
        public float amplitude = 0.06f;
        public float frequency = 1.5f;
        Vector3 _base;
        float _phase;

        void Start()
        {
            _base = transform.localPosition;
            _phase = Random.value * 10f;
        }

        void Update()
        {
            transform.localPosition = _base + Vector3.up * Mathf.Sin((Time.time + _phase) * frequency) * amplitude;
        }
    }
}
