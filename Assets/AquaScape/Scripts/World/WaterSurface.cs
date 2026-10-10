using UnityEngine;

namespace AquaScape
{
    /// <summary>
    /// Feeds the land mask from <see cref="TerrainPainter"/> into the water
    /// material, and rebuilds it whenever the terrain changes (e.g. a bridge).
    /// Runs in edit mode too so the scene view shows the finished water.
    /// </summary>
    [ExecuteAlways]
    [RequireComponent(typeof(SpriteRenderer))]
    public class WaterSurface : MonoBehaviour
    {
        public TerrainPainter terrain;

        static readonly int MaskTexId = Shader.PropertyToID("_MaskTex");
        static readonly int MaskRectId = Shader.PropertyToID("_MaskRect");

        MaterialPropertyBlock _block;

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

        void Apply()
        {
            var sr = GetComponent<SpriteRenderer>();
            _block ??= new MaterialPropertyBlock();
            sr.GetPropertyBlock(_block);
            _block.SetTexture(MaskTexId, terrain.LandMask);
            _block.SetVector(MaskRectId, terrain.LandMaskRect);
            sr.SetPropertyBlock(_block);
        }
    }
}
