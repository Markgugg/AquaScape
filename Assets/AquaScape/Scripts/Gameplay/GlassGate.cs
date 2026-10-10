using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// A wall of energy-glass panels that dissolves once every linked pressure
    /// pad is pressed. Each panel has its own collider so the gate can span
    /// any number of cells.
    /// </summary>
    public class GlassGate : MonoBehaviour
    {
        public List<PressurePad> pads = new List<PressurePad>();
        public List<SpriteRenderer> panels = new List<SpriteRenderer>();

        public bool IsOpen { get; private set; }

        void Update()
        {
            if (IsOpen || pads.Count == 0) return;
            foreach (var p in pads)
                if (!p.Pressed) return;
            StartCoroutine(OpenRoutine());
        }

        IEnumerator OpenRoutine()
        {
            IsOpen = true;
            yield return new WaitForSeconds(0.4f);
            Vector3 center = Vector3.zero;
            foreach (var p in panels) center += p.transform.position;
            center /= Mathf.Max(1, panels.Count);
            CameraFollow.Focus(center, 1.6f);
            yield return new WaitForSeconds(0.35f);
            AudioManager.Play("gate_open", 1f, 1f, center);
            UIManager.Toast("The glass gate opens", "");

            foreach (var col in GetComponentsInChildren<Collider2D>()) col.enabled = false;
            // panels sink and fade one after another
            for (float t = 0; t < 1.2f; t += Time.deltaTime)
            {
                for (int i = 0; i < panels.Count; i++)
                {
                    float k = Mathf.Clamp01((t - i * 0.08f) / 0.6f);
                    panels[i].transform.localScale = new Vector3(1f, 1f - k, 1f);
                    panels[i].color = new Color(1f, 1f, 1f, 1f - k);
                }
                yield return null;
            }
            foreach (var p in panels) p.gameObject.SetActive(false);
        }
    }
}
