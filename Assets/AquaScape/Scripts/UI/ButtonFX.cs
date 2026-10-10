using UnityEngine;
using UnityEngine.EventSystems;

namespace AquaScape
{
    // makes menu buttons bounce and click when you hover or press them
    public class ButtonFX : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler, IPointerDownHandler
    {
        float _target = 1f;

        // grow a bit on hover
        public void OnPointerEnter(PointerEventData e)
        {
            _target = 1.06f;
            AudioManager.Play("ui_hover");
        }

        public void OnPointerExit(PointerEventData e) => _target = 1f;

        // squish down on press
        public void OnPointerDown(PointerEventData e)
        {
            transform.localScale = Vector3.one * 0.94f;
            AudioManager.Play("ui_click");
        }

        // ease the scale back toward the target
        void Update()
        {
            transform.localScale = Vector3.Lerp(transform.localScale, Vector3.one * _target, Time.unscaledDeltaTime * 14f);
        }
    }
}
