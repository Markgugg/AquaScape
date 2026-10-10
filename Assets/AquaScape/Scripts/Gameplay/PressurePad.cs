using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace AquaScape
{
    // a floor pad that lights up when a glass cube slides onto it
    public class PressurePad : MonoBehaviour
    {
        // every pad in the scene
        static readonly List<PressurePad> s_pads = new List<PressurePad>();

        public SpriteRenderer sprite;
        public Sprite onSprite;
        public Light2D glow;

        public bool Pressed { get; private set; }
        // the grid cell the pad sits on
        public Vector3Int Cell { get; private set; }

        void OnEnable()
        {
            Cell = new Vector3Int(Mathf.FloorToInt(transform.position.x), Mathf.FloorToInt(transform.position.y), 0);
            s_pads.Add(this);
        }

        void OnDisable() => s_pads.Remove(this);

        // finds the pad on a cell, or null if there isnt one
        public static PressurePad At(Vector3Int cell)
        {
            foreach (var p in s_pads)
                if (p.Cell == cell) return p;
            return null;
        }

        // turns the pad on when a cube lands on it
        public void Press(GlassCube cube)
        {
            if (Pressed) return;
            Pressed = true;
            sprite.sprite = onSprite;
            if (glow != null) glow.intensity = 1.4f;
            AudioManager.Play("pad_on", 1f, 1f, transform.position);
            GameAssets.Burst(GameAssets.Instance != null ? GameAssets.Instance.sparkleFx : null, transform.position);
        }
    }
}
