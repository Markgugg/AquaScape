using UnityEngine;

namespace AquaScape
{
    // holds prefabs that get spawned during the game like bubbles and particle bursts
    public class GameAssets : MonoBehaviour
    {
        public static GameAssets Instance { get; private set; }

        // prefabs used by other scripts
        public Bubble bubblePrefab;
        public ParticleSystem popFx;
        public ParticleSystem sparkleFx;
        public ParticleSystem tileFx;
        public ParticleSystem poofFx;

        void Awake() => Instance = this;

        // spawns a one shot particle burst with an optional tint
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
