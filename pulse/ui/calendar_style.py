"""Neutral database-calendar tokens shared by the toolbar and painted grid."""
from pulse.ui.theme import ThemeManager


def calendar_colors():
    dark = ThemeManager.instance().current_name == 'dark'
    return dict(
        background='#191919' if dark else '#ffffff',
        text='#e6e6e4' if dark else '#37352f',
        muted='#999995' if dark else '#787774',
        line='#353535' if dark else '#e9e9e7',
        card='#262626' if dark else '#ffffff',
        hover='#333333' if dark else '#f1f1ef',
        outside='#202020' if dark else '#f7f7f5',
        today='#eb5757',
    )
