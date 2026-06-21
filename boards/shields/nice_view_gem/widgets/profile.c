#include <zephyr/kernel.h>
#include "profile.h"
#include "../assets/custom_fonts.h"

// Show the active BLE profile as a readable number ("BT 1".."BT 4") instead of
// the tiny 5-dot indicator. active_profile_index is 0-based, so display +1.
void draw_profile_status(lv_obj_t *canvas, const struct status_state *state) {
    lv_draw_label_dsc_t label_dsc;
    init_label_dsc(&label_dsc, LVGL_FOREGROUND, &pixel_operator_mono, LV_TEXT_ALIGN_CENTER);

    char text[8] = {};
    sprintf(text, "BT %i", state->active_profile_index + 1);

    canvas_draw_text(canvas, 0, 129 + BUFFER_OFFSET_BOTTOM, 68, &label_dsc, text);
}
