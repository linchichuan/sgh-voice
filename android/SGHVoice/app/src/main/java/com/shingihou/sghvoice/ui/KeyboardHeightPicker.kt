package com.shingihou.sghvoice.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.KeyboardSizing
import kotlin.math.roundToInt

@Composable
fun KeyboardHeightPicker(percent: Int, onChange: (Int) -> Unit) {
    val title = stringResource(R.string.keyboard_height_title)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.keyboard_height_hint), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(R.string.keyboard_height_value, percent))
            Slider(
                value = percent.toFloat(),
                onValueChange = { onChange(KeyboardSizing.normalize(it.roundToInt())) },
                valueRange = KeyboardSizing.MIN_PERCENT.toFloat()..KeyboardSizing.MAX_PERCENT.toFloat(),
                steps = 6,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).semantics { contentDescription = title }
            )
            TextButton(onClick = { onChange(KeyboardSizing.DEFAULT_PERCENT) },
                modifier = Modifier.heightIn(min = 48.dp)) {
                Text(stringResource(R.string.keyboard_height_reset))
            }
        }
    }
}
