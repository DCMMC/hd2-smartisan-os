/*
 * ngfd - Non-graphic feedback daemon
 *
 * Copyright (C) 2010 Nokia Corporation.
 * Contact: Xun Chen <xun.chen@nokia.com>
 * Copyright (C) 2014,2017 Jolla Ltd.
 * Contact: Simonas Leleiva <simonas.leleiva@jollamobile.com>
 *
 * This work is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This work is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this work; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
 */

#include <ngf/plugin.h>
#include <ngf/haptic.h>

#include "implementation.h"

#define AV_KEY "plugin.droid-vibrator.data"

#define EFFECT_LIST             "EFFECT_LIST"
#define EFFECT_LIST_DELIMITER   ","
#define EFFECT_VIBRA            "on"
#define EFFECT_PAUSE            "pause"
#define EFFECT_REPEAT           "repeat"
#define EFFECT_REPEAT_FOREVER   "forever"
#define MAX_STEP_TIME           (10000) /* 10 seconds */
#define MIN_STEP_TIME           (1)     /* 1 ms */
#define MAX_REPEATS             (100)
#define REPEAT_FOREVER          (-1)
#define HAPTIC_DURATION         "haptic.duration"
#define EFFECT_SEQUENCE         "haptic.sequence"

enum EffectStepType {
    EFFECT_STEP_NONE,
    /* vibrator on for *value* ms */
    EFFECT_STEP_VIBRA,
    /* pause for *value* ms */
    EFFECT_STEP_PAUSE,
    /* repeat the whole sequence from the beginning of
       the sqeuence *value* times,
       -1 forever, 0 no repeat, 1+ n repeats */
    EFFECT_STEP_REPEAT
};

typedef struct DroidVibratorEffectStep
{
    enum EffectStepType type;
    int                 value;
} DroidVibratorEffectStep;

typedef struct DroidVibratorEffect
{
    GSList             *steps;
    int                 repeat;
} DroidVibratorEffect;

typedef struct DroidVibratorData
{
    NRequest               *request;
    NSinkInterface         *iface;
    guint                   sequence_id;
    DroidVibratorEffect    *current_effect;
    GSList                 *current_step;
    guint                   remaining;
    int                     repeat_count;
    /* Effect is parsed for the event and freed after use. */
    gboolean                one_shot;
} DroidVibratorData;

static GHashTable      *plugin_effects;

N_PLUGIN_NAME        ("droid-vibrator")
N_PLUGIN_VERSION     ("0.3")
N_PLUGIN_DESCRIPTION (IMPLEMENTATION_DESCRIPTION)

static void
effect_free (gpointer data)
{
    DroidVibratorEffect *effect = (DroidVibratorEffect*) data;
    g_slist_free_full (effect->steps, g_free);
    g_free (effect);
}

static DroidVibratorEffect*
effect_parse (const char *sequence)
{
    DroidVibratorEffect *effect = NULL;
    gchar **sequence_parts = NULL;
    int i;

    if (!sequence || !*sequence)
        return NULL;

    sequence_parts = g_strsplit(sequence, EFFECT_LIST_DELIMITER, 0);

    effect = g_new0 (DroidVibratorEffect, 1);

    for (i = 0; sequence_parts[i]; i++) {
        enum EffectStepType step_type = EFFECT_STEP_NONE;
        DroidVibratorEffectStep *s;
        gchar **step;
        gint64 value;

        step = g_strsplit(sequence_parts[i], "=", 0);
        if (!step[0] || !step[1]) {
            g_strfreev (step);
            effect_free (effect);
            effect = NULL;
            N_WARNING (LOG_CAT "bad sequence string '%s', ignoring sequence", sequence);
            goto done;
        }

        if (g_strcmp0 (step[0], EFFECT_VIBRA) == 0)
            step_type = EFFECT_STEP_VIBRA;
        else if (g_strcmp0 (step[0], EFFECT_PAUSE) == 0)
            step_type = EFFECT_STEP_PAUSE;
        else if (g_strcmp0 (step[0], EFFECT_REPEAT) == 0)
            step_type = EFFECT_STEP_REPEAT;

        switch (step_type) {
            case EFFECT_STEP_VIBRA:
            /* fall through */
            case EFFECT_STEP_PAUSE:
                s = g_new0 (DroidVibratorEffectStep, 1);
                s->type = step_type;
                value = g_ascii_strtoll (step[1], NULL, 10);
                if (value > MAX_STEP_TIME)
                    value = MAX_STEP_TIME;
                else if (value < MIN_STEP_TIME)
                    value = MIN_STEP_TIME;
                s->value = (int) value;
                effect->steps = g_slist_append (effect->steps, s);
                break;

            case EFFECT_STEP_REPEAT:
                if (g_strcmp0 (step[1], EFFECT_REPEAT_FOREVER) == 0)
                    value = REPEAT_FOREVER;
                else {
                    value = g_ascii_strtoll (step[1], NULL, 10);
                    if (value > MAX_REPEATS)
                        value = MAX_REPEATS;
                    else if (value <= -1)
                        value = REPEAT_FOREVER;
                }
                effect->repeat = (int) value;
                break;

            default:
                N_WARNING (LOG_CAT "incorrect sequence type %s, ignoring", step[0]);
                break;
        }

        g_strfreev (step);
    }

done:
    g_strfreev (sequence_parts);

    if (effect && !effect->steps) {
        N_WARNING (LOG_CAT "no valid effect steps, ignoring sequence '%s'", sequence);
        effect_free (effect);
        effect = NULL;
    }

    return effect;
}

static DroidVibratorEffect*
effect_parse_from_proplist (const char *name, const NProplist *properties)
{
    const gchar *sequence = NULL;

    if (!(sequence = n_proplist_get_string (properties, name))) {
        N_WARNING (LOG_CAT "sequence missing for %s", name);
        return NULL;
    }

    return effect_parse (sequence);
}

static GHashTable*
effects_parse (const NProplist *properties)
{
    GHashTable *effects = NULL;
    const gchar *effect_data;
    gchar **effect_names;
    int i;

    effect_data = n_proplist_get_string (properties, EFFECT_LIST);

    if (!effect_data) {
        N_WARNING (LOG_CAT "no " EFFECT_LIST " defined");
        return NULL;
    }

    effect_names = g_strsplit (effect_data, EFFECT_LIST_DELIMITER, 0);
    if (!effect_names[0]) {
        N_WARNING (LOG_CAT "Empty " EFFECT_LIST "string");
        goto effect_list_done;
    }

    N_DEBUG (LOG_CAT "creating effect list for %s", effect_data);

    effects = g_hash_table_new_full (g_str_hash,
                                     g_str_equal,
                                     g_free,
                                     effect_free);

    for (i = 0; effect_names[i]; i++) {
        DroidVibratorEffect *e;
        if ((e = effect_parse_from_proplist (effect_names[i], properties)))
            g_hash_table_insert (effects, g_strdup(effect_names[i]), e);
    }

effect_list_done:
    g_strfreev(effect_names);

    return effects;
}

static int
droid_vibrator_sink_can_handle (NSinkInterface *iface, NRequest *request)
{
    N_DEBUG (LOG_CAT "sink can_handle");
    return n_haptic_can_handle (iface, request);
}

static int
droid_vibrator_sink_prepare (NSinkInterface *iface, NRequest *request)
{
    DroidVibratorData *data;
    DroidVibratorEffect *effect;
    gboolean one_shot = FALSE;
    const gchar *key;
    const gchar *sequence;
    const NProplist *properties = n_request_get_properties (request);

    N_DEBUG (LOG_CAT "sink prepare");

    if ((sequence = n_proplist_get_string (properties, EFFECT_SEQUENCE))) {
        effect = effect_parse (sequence);
        if (!effect) {
            N_DEBUG (LOG_CAT "invalid effect sequence: %s", sequence);
            return FALSE;
        }
        one_shot = TRUE;
    } else {
        if (!(key = n_haptic_effect_for_request (request))) {
            N_DEBUG (LOG_CAT "no effect key found for this request");
            return FALSE;
        }

        if (!(effect = g_hash_table_lookup (plugin_effects, key))) {
            N_DEBUG (LOG_CAT "no effect with key %s found for this effect", key);
            return FALSE;
        }
    }

    data = g_slice_new0 (DroidVibratorData);
    data->request        = request;
    data->iface          = iface;
    data->sequence_id    = 0;
    data->current_effect = effect;
    data->current_step   = effect->steps;
    data->remaining      = n_proplist_get_uint (properties, HAPTIC_DURATION);
    data->repeat_count   = data->remaining ? REPEAT_FOREVER : effect->repeat;
    data->one_shot       = one_shot;

    n_request_store_data (request, AV_KEY, data);
    n_sink_interface_synchronize (iface, request);

    return TRUE;
}

static void
sequence_play (DroidVibratorData *data);

static gboolean
sequence_cb (gpointer userdata)
{
    DroidVibratorData *data = (DroidVibratorData*) userdata;
    g_assert (data);

    data->sequence_id = 0;
    data->current_step = g_slist_next (data->current_step);
    sequence_play (data);

    return FALSE;
}

static void
sequence_play (DroidVibratorData *data)
{
    DroidVibratorEffectStep *step;
    guint duration;

    if (!data->current_step) {
        if (data->repeat_count == REPEAT_FOREVER)
            data->current_step = data->current_effect->steps;
        else if (data->repeat_count > 0) {
            data->repeat_count--;
            data->current_step = data->current_effect->steps;
        } else {
            n_sink_interface_complete (data->iface, data->request);
            return;
        }
    }

    step = g_slist_nth_data (data->current_step, 0);

    if (data->remaining) {
        /* If remaining duration was specified, clamp step length to it and
           decrease remaining by that value. If remaining runs out, stop the
           effect. */
        if (data->remaining > step->value) {
            if (step->type == EFFECT_STEP_VIBRA && !g_slist_next(data->current_effect->steps))
                /* If the effect consists only of single vibration sequence,
                   play it as long as possible. */
                duration = data->remaining < MAX_STEP_TIME ? data->remaining : MAX_STEP_TIME;
            else
                duration = step->value;
        } else
            duration = data->remaining;
        data->remaining -= duration;
        if (data->remaining == 0) {
            data->current_step = NULL;
            data->repeat_count = 0;
        }
    } else {
        duration = step->value;
    }
    data->sequence_id = g_timeout_add (duration, sequence_cb, data);
    if (step->type == EFFECT_STEP_VIBRA)
        h_vibrator_on (duration);
}

static int
droid_vibrator_sink_play (NSinkInterface *iface, NRequest *request)
{
    DroidVibratorData *data;
    (void) iface;

    N_DEBUG (LOG_CAT "sink play");

    data = (DroidVibratorData*) n_request_get_data (request, AV_KEY);
    g_assert (data);
    sequence_play (data);

    return TRUE;
}

static void
sequence_stop (DroidVibratorData *data)
{
    if (data->sequence_id > 0) {
        g_source_remove (data->sequence_id);
        data->sequence_id = 0;
        h_vibrator_off ();
    }
}

static int
droid_vibrator_sink_pause (NSinkInterface *iface, NRequest *request)
{
    DroidVibratorData *data;
    (void) iface;

    N_DEBUG (LOG_CAT "sink pause");

    data = (DroidVibratorData*) n_request_get_data (request, AV_KEY);
    g_assert (data);
    sequence_stop (data);

    return TRUE;
}

static void
droid_vibrator_sink_stop (NSinkInterface *iface, NRequest *request)
{
    DroidVibratorData *data;
    (void) iface;

    N_DEBUG (LOG_CAT "sink stop");

    data = (DroidVibratorData*) n_request_get_data (request, AV_KEY);
    g_assert (data);
    sequence_stop (data);
    if (data->one_shot)
        effect_free (data->current_effect);
    g_slice_free (DroidVibratorData, data);
}

N_PLUGIN_LOAD (plugin)
{
    const NProplist *properties;

    static const NSinkInterfaceDecl decl = {
        .name       = IMPLEMENTATION_NAME,
        .type       = N_SINK_INTERFACE_TYPE_VIBRATOR,
        .initialize = NULL,
        .shutdown   = NULL,
        .can_handle = droid_vibrator_sink_can_handle,
        .prepare    = droid_vibrator_sink_prepare,
        .play       = droid_vibrator_sink_play,
        .pause      = droid_vibrator_sink_pause,
        .stop       = droid_vibrator_sink_stop
    };

    properties = n_plugin_get_params (plugin);
    g_assert (properties);

    if (h_vibrator_open (properties) < 0)
        return FALSE;

    plugin_effects = effects_parse (properties);

    if (!plugin_effects)
        return FALSE;

    n_plugin_register_sink (plugin, &decl);

    return TRUE;
}

N_PLUGIN_UNLOAD (plugin)
{
    (void) plugin;

    if (plugin_effects) {
        g_hash_table_destroy (plugin_effects);
        plugin_effects = NULL;
    }

    h_vibrator_close ();
}
