using System.Collections;
using UnityEngine;

namespace AquaScape
{
    /// <summary>A pearly clam that springs open when pulsed and releases bubbles.</summary>
    public class BubbleClam : PulseTarget
    {
        [SerializeField] int bubbleCount = 5;
        public SpriteRenderer sprite;
        public Sprite openSprite;

        public int BubbleCount => bubbleCount;
        bool _open;

        public override bool ShowsPrompt => !_open;

        public override void OnPulse(Vector2 origin)
        {
            if (_open) return;
            _open = true;
            StartCoroutine(OpenRoutine());
        }

        IEnumerator OpenRoutine()
        {
            AudioManager.Play("clam_open", Random.Range(0.96f, 1.04f), 1f, transform.position);
            // squash, swap sprite, spring back
            float t = 0f;
            while (t < 0.12f)
            {
                t += Time.deltaTime;
                sprite.transform.localScale = new Vector3(1f + t * 1.5f, 1f - t * 1.8f, 1f);
                yield return null;
            }
            sprite.sprite = openSprite;
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.sparkleFx : null, transform.position + Vector3.up * 0.4f);

            // scatter bubbles in a ring around the clam, landing on walkable cells
            for (int i = 0; i < bubbleCount; i++)
            {
                float a = (i / (float)bubbleCount) * Mathf.PI * 2f + Random.Range(-0.3f, 0.3f);
                Vector3 to = transform.position + new Vector3(Mathf.Cos(a), Mathf.Sin(a) * 0.8f, 0f) * Random.Range(0.9f, 1.4f);
                if (TerrainPainter.Instance != null && !TerrainPainter.Instance.IsWalkable(TerrainPainter.Instance.WorldToCell(to)))
                    to = transform.position + (to - transform.position) * 0.4f;
                Bubble.Spawn(transform.position + Vector3.up * 0.2f, to, 0.45f + i * 0.04f);
            }

            t = 0f;
            while (t < 0.35f)
            {
                t += Time.deltaTime;
                float k = t / 0.35f;
                float s = 1f + Mathf.Sin(k * Mathf.PI * 2.5f) * 0.12f * (1f - k);
                sprite.transform.localScale = new Vector3(s, 2f - s, 1f);
                yield return null;
            }
            sprite.transform.localScale = Vector3.one;
        }
    }
}
