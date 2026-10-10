using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace AquaScape
{
    // a glass wall that opens once all its pressure pads are pressed
    public class GlassGate : MonoBehaviour
    {
        // pads that all need to be pressed
        public List<PressurePad> pads = new List<PressurePad>();
        // the glass pieces of the wall, each one has its own collider
        public List<SpriteRenderer> panels = new List<SpriteRenderer>();

        public bool IsOpen { get; private set; }

        // opens the gate when every pad is pressed
        void Update()
        {
            if (IsOpen || pads.Count == 0) return;
            foreach (var p in pads)
                if (!p.Pressed) return;
            StartCoroutine(OpenRoutine());
        }

        // shows the gate on camera, turns off the colliders and fades the panels
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
