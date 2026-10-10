using UnityEngine;

namespace AquaScape
{
    // gives the water material the land mask and updates it when the terrain changes
    // runs in edit mode too so the scene view shows the water
    [ExecuteAlways]
    [RequireComponent(typeof(SpriteRenderer))]
    public class WaterSurface : MonoBehaviour
    {
        // the terrain that makes the land mask
        public TerrainPainter terrain;

        void OnEnable()
        {
            if (terrain == null) return;
            terrain.MaskRebuilt += Apply;
            terrain.BuildLandMask();
        }

        void OnDisable()
        {
            if (terrain != null) terrain.MaskRebuilt -= Apply;
        }

        // sends the mask texture and its world rect to the shader
        void Apply()
        {
            var sr = GetComponent<SpriteRenderer>();
            var block = new MaterialPropertyBlock();
            sr.GetPropertyBlock(block);
            block.SetTexture("_MaskTex", terrain.LandMask);
            block.SetVector("_MaskRect", terrain.LandMaskRect);
            sr.SetPropertyBlock(block);
        }
    }
}
