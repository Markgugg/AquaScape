using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// A glass bridge that does not exist yet. When activated it lays glass
    /// walkway cells one by one (with rising chimes and sparkles) while the
    /// camera briefly looks at it, then refreshes the water's shoreline mask.
    /// </summary>
    public class BridgeBuilder : MonoBehaviour
    {
        [Tooltip("World cells of the bridge, in the order they should appear.")]
        public List<Vector2Int> cells = new List<Vector2Int>();
        public float tileInterval = 0.07f;
        public bool focusCamera = true;

        public bool Built { get; private set; }
        public event Action Completed;

        public void Activate(float delay = 0.5f)
        {
            if (Built) return;
            Built = true;
            StartCoroutine(BuildRoutine(delay));
        }

        public Vector3 Center
        {
            get
            {
                if (cells.Count == 0) return transform.position;
                Vector2 sum = Vector2.zero;
                foreach (var c in cells) sum += c;
                return (Vector3)(sum / cells.Count) + new Vector3(0.5f, 0.5f, 0f);
            }
        }

        IEnumerator BuildRoutine(float delay)
        {
            yield return new WaitForSeconds(delay);
            float total = cells.Count * tileInterval;
            if (focusCamera)
            {
                CameraFollow.Focus(Center, total + 0.9f);
                PlayerController.Instance?.Freeze(total + 0.6f);
            }
            yield return new WaitForSeconds(0.35f);

            var terrain = TerrainPainter.Instance;
            for (int i = 0; i < cells.Count; i++)
            {
                var c = new Vector3Int(cells[i].x, cells[i].y, 0);
                terrain.SetCell(TerrainPainter.Layer.Glass, c, true);
                Vector3 p = TerrainPainter.CellCenter(c);
                GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.tileFx : null, p);
                AudioManager.Play("bridge_tile", 1f + 0.6f * i / Mathf.Max(1, cells.Count - 1), 0.8f, p);
                yield return new WaitForSeconds(tileInterval);
            }
            terrain.BuildLandMask();
            AudioManager.Play("bridge_complete", 1f, 1f, Center);
            CameraFollow.Shake(0.05f, 0.2f);
            Completed?.Invoke();
        }
    }
}
