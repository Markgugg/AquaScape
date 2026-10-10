using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Scene-wide references to prefabs that gameplay code spawns at runtime
    /// (bubbles, particle bursts), plus a helper for one-shot effects.
    /// </summary>
    public class GameAssets : MonoBehaviour
    {
        public static GameAssets Instance { get; private set; }

        public Bubble bubblePrefab;
        public ParticleSystem popFx;
        public ParticleSystem sparkleFx;
        public ParticleSystem tileFx;
        public ParticleSystem poofFx;

        void Awake() => Instance = this;

        /// <summary>Spawn a particle burst prefab that destroys itself when done.</summary>
        public static void Burst(ParticleSystem prefab, Vector3 position, Color? tint = null)
        {
            if (prefab == null) return;
            var fx = Instantiate(prefab, position, Quaternion.identity);
            if (tint.HasValue)
            {
                var main = fx.main;
                main.startColor = tint.Value;
            }
            fx.Play();
        }
    }
}
