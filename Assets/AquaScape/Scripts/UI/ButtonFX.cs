using UnityEngine;
using UnityEngine.EventSystems;

namespace AquaScape
{
    /// <summary>Glassy hover/press feedback for menu buttons: a soft scale bounce and tick sounds.</summary>
    public class ButtonFX : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler, IPointerDownHandler
    {
        float _target = 1f;

        public void OnPointerEnter(PointerEventData e)
        {
            _target = 1.06f;
            AudioManager.Play("ui_hover");
        }

        public void OnPointerExit(PointerEventData e) => _target = 1f;

        public void OnPointerDown(PointerEventData e)
        {
            transform.localScale = Vector3.one * 0.94f;
            AudioManager.Play("ui_click");
        }

        void Update()
        {
            transform.localScale = Vector3.Lerp(transform.localScale, Vector3.one * _target, Time.unscaledDeltaTime * 14f);
        }
    }
}
