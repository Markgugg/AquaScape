using UnityEngine;

namespace AquaScape
{
    // keeps ambient particle emitters centered on the camera
    public class FollowCamera : MonoBehaviour
    {
        // extra offset from the camera position
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
