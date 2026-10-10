using UnityEngine;

namespace AquaScape
{
    /// <summary>Keeps ambient particle emitters centred on the camera view.</summary>
    public class FollowCamera : MonoBehaviour
    {
        public Vector3 offset;

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null) return;
            var p = cam.transform.position + offset;
            transform.position = new Vector3(p.x, p.y, 0f);
        }
    }
}
