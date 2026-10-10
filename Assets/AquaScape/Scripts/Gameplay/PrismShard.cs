using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// The Prism Shard of an area: picking it up lets the player light that
    /// area's beacon. Spins/bobs with a glow so it reads as important.
    /// </summary>
    public class PrismShard : MonoBehaviour
    {
        public int zone;
        public Transform visual;
        public float pickupRadius = 0.9f;

        void Update()
        {
            if (visual != null)
            {
                visual.localPosition = new Vector3(0f, 0.55f + Mathf.Sin(Time.time * 2.4f) * 0.1f, 0f);
                // fake a slow spin by squashing the x scale
                float spin = Mathf.Cos(Time.time * 2.2f);
                visual.localScale = new Vector3(0.75f + 0.25f * Mathf.Abs(spin), 1f, 1f);
            }

            var player = PlayerController.Instance;
            if (player == null || (GameManager.Instance != null && !GameManager.Instance.IsPlaying)) return;
            if (Vector2.Distance(player.transform.position, transform.position) < pickupRadius)
                Collect();
        }

        void Collect()
        {
            GameManager.Instance?.CollectShard(zone);
            AudioManager.Play("shard_pickup", 1f, 1f, transform.position);
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.sparkleFx : null, transform.position + Vector3.up * 0.55f);
            CameraFollow.Shake(0.08f, 0.2f);
            UIManager.Toast("Prism Shard found!", "Bring it to the Beacon and pulse it");
            Destroy(gameObject);
        }
    }
}
