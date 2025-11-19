import datetime
import logging
from collections import defaultdict
from itertools import zip_longest
from typing import Literal
from uuid import UUID

from PySide6.QtCore import QDate, QLocale, QTime, QCoreApplication
from PySide6.QtWidgets import QWidget

from configuration.general_settings import general_settings_handler
from database import db_services, schemas

logger = logging.getLogger(__name__)

# date_to_string cache:
_locale_cache = {}
_position_separator_cache = {}


def get_cached_locale(country: QLocale.Country, language: QLocale.Language) -> QLocale:
    """Gibt die Locale für das angegebene Land und die angegebene Sprache zurück."""
    cache_key = (country, language)
    if cache_key not in _locale_cache:
        if locales := QLocale.matchingLocales(language, QLocale.Script.AnyScript, country):
            _locale_cache[cache_key] = locales[0]
        else:
            _locale_cache[cache_key] = QLocale()
    return _locale_cache[cache_key]


def backtranslate_eval_str(fixed_cast: str, str_for_team: str = 'team'):
    form = []
    eval_str = fixed_cast
    if not eval_str:
        return
    e_s = eval_str.replace('and', ',"and",').replace('or', ',"or",').replace(f'in {str_for_team}', '')
    e_s = eval(e_s)
    if type(e_s) != tuple:
        e_s = (e_s,)
    for element in e_s:
        if type(element) == tuple:
            break
    else:
        e_s = [e_s]
    for val in e_s:
        if type(val) in [int, UUID]:
            form.append([val])
        elif type(val) == str:
            form.append(val)
        else:
            form.append(list(val))
    return form


def generate_fixed_cast_clear_text(fixed_cast: str | None, only_if_available: bool = False):
    replace_map = {'and': QCoreApplication.translate('generate_fixed_cast_clear_text', 'and'),
                   'or': QCoreApplication.translate('generate_fixed_cast_clear_text', 'or')}

    def generate_recursive(item_list: list):
        clear_list = []
        for item in item_list:
            if isinstance(item, str):
                clear_list.append(replace_map[item])
            elif isinstance(item, UUID):
                person = db_services.Person.get(item)
                clear_list.append(f'{person.f_name} {person.l_name}')
            else:
                clear_list.append(str(generate_recursive(item)))
        return clear_list[0] if len(clear_list) == 1 else '(' + ' '.join(clear_list) + ')'
    item = backtranslate_eval_str(fixed_cast)
    clear_text = generate_recursive(item or [])
    if clear_text.startswith('('):
        clear_text = clear_text[1:]
    if clear_text.endswith(')'):
        clear_text = clear_text[:-1]

    clear_text += QCoreApplication.translate('generate_fixed_cast_clear_text',
                                             ' (if available)') if only_if_available else ''

    return clear_text


def get_appointments_of_actors_from_plan(plan: schemas.PlanShow) -> dict[str, list[schemas.Appointment]]:
    pp: schemas.PlanPeriodShow
    name_appointments: defaultdict[str, list[schemas.Appointment]] = defaultdict(list)
    for appointment in plan.appointments:
        for avail_day in appointment.avail_days:
            name_appointments[avail_day.actor_plan_period.person.full_name].append(appointment)
        for name in appointment.guests:
            name_appointments[name].append(appointment)
    for appointments in name_appointments.values():
        appointments.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))

    return {name: name_appointments[name] for name in sorted(name_appointments.keys())}


def get_appointments_of_all_actors_from_plan(
        plan: schemas.PlanShow) -> dict[str, tuple[schemas.ActorPlanPeriod | None, list[schemas.Appointment]]]:
    actor_plan_periods = db_services.ActorPlanPeriod.get_all_from__plan_period(plan.plan_period.id)
    actor_ids_between_dates = db_services.TeamActorAssign.get_all_actor_ids_between_dates(
        plan.plan_period.team.id, plan.plan_period.start, plan.plan_period.end)
    result: dict[str, tuple[schemas.ActorPlanPeriod | None, list[schemas.Appointment]]] = {
        app.person.full_name: (app, []) for app in actor_plan_periods
        if app.person.id in actor_ids_between_dates
    }
    for appointment in plan.appointments:
        for avail_day in appointment.avail_days:
            result[avail_day.actor_plan_period.person.full_name][1].append(appointment)
        for name in appointment.guests:
            if not result.get(name):
                result[name] = (None, [])
            result[name][1].append(appointment)
    for _, appointments in result.values():
        appointments.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))

    return {name: result[name] for name in sorted(result.keys())}


def n_th_weekday_of_period(start: datetime.date, end: datetime.date, weekday: int, n: int) -> datetime.date | None:
    """
    Bestimm den n-ten Wochentag in einem Zeitraum.
    weekdays: (0 = Montag, ..., 6 = Sonntag)
    """
    if n < 1:
        return None
    # Berechnung des ersten Wochentags
    delta_days = (weekday - start.weekday()) % 7
    date_of_first_weekday = start + datetime.timedelta(days=delta_days)
    # Berechnung des n-ten Wochentags
    if (date_of_n_th_weekday := (date_of_first_weekday + datetime.timedelta(days=7 * (n - 1)))) > end:
        return None
    return date_of_n_th_weekday


def datetime_date_to_qdate(date: datetime.date) -> QDate:
    """Konvertiert ein datetime.date-Objekt in ein QDate-Objekt."""
    return QDate(date.year, date.month, date.day)


def date_to_string(date: datetime.date, to_html: bool = False, curr_country: QLocale.Country | None = None,
                   curr_language: QLocale.Language | None = None, curr_format: QLocale.FormatType | None = None) -> str:
    """
    Gibt das Datum in der von der Anwendung gewünschten Formatierung zurück.
    Falls curr_country, curr_language oder curr_format nicht angegeben, werden die Werte aus den Einstellungen genommen.
    """

    def get_cached_positions_and_separator(curr_format: QLocale.FormatType,
                                           locale: QLocale) -> tuple[int, int, int, str] | None:
        """Gibt die Positionen der Jahreszahl, Monatszahl und Tageszahl im Format und den Separator zurück."""
        cache_key = (curr_format, locale)
        if cache_key not in _position_separator_cache:
            ref_date = QDate(2099, 12, 31)
            ref_formatted = locale.toString(ref_date, curr_format)
            
            if separator := next((char for char in ref_formatted if not char.isdigit()), None):
                ref_parts = ref_formatted.split(separator)
                stripped_ref_parts = ref_parts  # [p.strip() for p in ref_parts]
                try:
                    month_pos, day_pos = stripped_ref_parts.index("12"), stripped_ref_parts.index("31")
                    year_pos = ({0, 1, 2} - {month_pos, day_pos}).pop()
                    _position_separator_cache[cache_key] = (year_pos, month_pos, day_pos, separator)
                except ValueError:
                    _position_separator_cache[cache_key] = None
            else:
                _position_separator_cache[cache_key] = None
        return _position_separator_cache[cache_key]

    def format_date_html(date_str: str, position_separator: tuple[int, int, int, str]) -> str:
        """Formatiert das Datum in HTML, um den Tag hervorzuheben."""
        year_pos, month_pos, day_pos, separator = position_separator
        date_list = date_str.split(separator)
        date_list[day_pos] = f'<span style="font-size: 11pt; font-weight: bold;">{date_list[day_pos]}</span>'
        date_list[month_pos] = f'<span style="font-size: 11pt;">{date_list[month_pos]}</span>'
        return separator.join(date_list)

    # Hauptlogik
    q_date = datetime_date_to_qdate(date)
    if not (curr_country and curr_language and curr_format):
        date_format_settings = general_settings_handler.get_general_settings().date_format_settings
        curr_country = QLocale.Country(date_format_settings.country)
        curr_language = QLocale.Language(date_format_settings.language)
        curr_format = QLocale.FormatType(date_format_settings.format)
    
    locale = get_cached_locale(curr_country, curr_language)
    position_separator = (get_cached_positions_and_separator(curr_format, locale)
                        if curr_format in [QLocale.FormatType.ShortFormat, QLocale.FormatType.NarrowFormat]
                        else None)

    if curr_format == QLocale.FormatType.ShortFormat:
        # Eventuelle 2-stellige Jahreszahl soll in 4-stellige Jahreszahl umgewandelt werden.
        formatted_date = locale.toString(q_date, curr_format)
        full_year = str(q_date.year())
        
        if full_year not in formatted_date and position_separator:
            year_pos, *_, separator = position_separator
            parts = formatted_date.split(separator)
            parts[year_pos] = full_year
            formatted_date = separator.join(parts)
    else:
        formatted_date = locale.toString(q_date, curr_format)

    if to_html and position_separator and curr_format in [QLocale.FormatType.ShortFormat, QLocale.FormatType.NarrowFormat]:
        return format_date_html(formatted_date, position_separator)
    return formatted_date


def time_to_string(time: datetime.time, curr_country: QLocale.Country | None = None,
                   curr_language: QLocale.Language | None = None, curr_format: QLocale.FormatType | None = None) -> str:
    """
    Gibt die Zeit in der von der Anwendung gewünschten Formatierung zurück.
    Es werden die Werte von curr_country, curr_language und curr_format aus den Einstellungen genommen.
    """
    if not (curr_country and curr_language and curr_format):
        date_format_settings = general_settings_handler.get_general_settings().date_format_settings
        curr_country = QLocale.Country(date_format_settings.country)
        curr_language = QLocale.Language(date_format_settings.language)
        curr_format = QLocale.FormatType(date_format_settings.format)

    locale = get_cached_locale(
        QLocale.Country(curr_country),
        QLocale.Language(curr_language)
    )
    return locale.toString(QTime(time.hour, time.minute), QLocale.FormatType(curr_format))


def setup_form_help(form_widget: QWidget, form_name: str, add_help_button: bool = False,
                   help_button_style: Literal["auto", "titlebar", "buttonbox", "floating"] = "titlebar") -> bool:
    """
    Richtet standardmäßig Hilfe für ein Formular ein.
    
    Args:
        form_widget: Das QWidget/QMainWindow Formular
        form_name: Name des Formulars für die Hilfe-Seite
        add_help_button: Ob ein ?-Button hinzugefügt werden soll
        help_button_style: Stil des Help-Buttons ("auto", "titlebar", "buttonbox", "floating")
        
    Returns:
        bool: True wenn Help-Integration erfolgreich, False bei Fehlern
    """
    try:
        from help import get_help_manager, HelpIntegration
        from PySide6.QtCore import Qt, QEvent
        from PySide6.QtWidgets import QDialogButtonBox, QWhatsThis
        
        help_manager = get_help_manager()
        
        if not help_manager:
            from help import init_help_system
            help_manager = init_help_system()
        
        if help_manager:
            help_integration = HelpIntegration(help_manager)
            
            # F1-Shortcut einrichten (wie bisher)
            help_integration.setup_f1_shortcut(form_widget, form_name=form_name)
            
            # Optional: ?-Button hinzufügen
            if add_help_button:
                
                # Auto-Detection des besten Stils
                if help_button_style == "auto":
                    button_boxes = form_widget.findChildren(QDialogButtonBox)
                    if button_boxes:
                        help_button_style = "buttonbox"
                    else:
                        help_button_style = "titlebar"
                
                if help_button_style == "titlebar":
                    # Windows-Style Help-Button in der Titelleiste
                    current_flags = form_widget.windowFlags()
                    
                    # Context Help Button hinzufügen
                    new_flags = current_flags | Qt.WindowType.WindowContextHelpButtonHint
                    form_widget.setWindowFlags(new_flags)
                    
                    # Form-Name als Widget-Attribut speichern (verhindert Closure-Problem)
                    form_widget._help_form_name = form_name
                    
                    # Event-Handler für Help-Button - NUR EINMAL setzen
                    if not hasattr(form_widget, '_help_event_handler_set'):
                        original_event = getattr(form_widget, 'event', None)
                        
                        def new_event(self, event):
                            # KORREKT: EnterWhatsThisMode abfangen (wird beim ?-Klick ausgelöst)
                            if event.type() == QEvent.Type.EnterWhatsThisMode:
                                # NUR verarbeiten wenn dieses Widget aktiv/fokussiert ist
                                if self.isActiveWindow() or self.hasFocus():
                                    # Aus Widget-Attribut lesen (verhindert Closure-Capture)
                                    if hasattr(self, '_help_form_name'):
                                        help_manager.show_help_for_form(self._help_form_name)
                                    # WhatsThis-Modus beenden
                                    QWhatsThis.leaveWhatsThisMode()
                                    # Event konsumieren - Propagation stoppen
                                    event.accept()
                                    return True
                                else:
                                    # Inaktive Widgets ignorieren Event
                                    return False
                            
                            # Standard Event-Handling
                            if original_event:
                                return original_event(event)
                            else:
                                return super(type(form_widget), self).event(event)
                        
                        # Event-Method ersetzen - NUR EINMAL
                        import types
                        form_widget.event = types.MethodType(new_event, form_widget)
                        form_widget._help_event_handler_set = True
                    
                    # Event-Method ersetzen
                    import types
                    form_widget.event = types.MethodType(new_event, form_widget)
                    
                elif help_button_style == "buttonbox":
                    # Hilfe-Button in QDialogButtonBox integrieren
                    button_boxes = form_widget.findChildren(QDialogButtonBox)
                    for button_box in button_boxes:
                        help_button = button_box.addButton("?", QDialogButtonBox.ButtonRole.HelpRole)
                        help_button.setToolTip("Hilfe anzeigen (F1)")
                        help_button.setMaximumSize(30, 25)
                        help_button.clicked.connect(
                            lambda: help_manager.show_help_for_form(form_name)
                        )
                        break
                
                elif help_button_style == "floating":
                    # Fallback: Floating Button
                    help_button = help_integration.create_help_button(form_widget, form_name, "?")
                    help_button.setStyleSheet("""
                        QPushButton {
                            background-color: #f0f0f0;
                            border: 1px solid #c0c0c0;
                            border-radius: 15px;
                            font-weight: bold;
                            color: #666;
                        }
                        QPushButton:hover {
                            background-color: #e0e0e0;
                            color: #333;
                        }
                    """)
                    
                    def position_help_button():
                        parent_rect = form_widget.rect()
                        button_size = 30
                        margin = 10
                        x = parent_rect.width() - button_size - margin
                        y = margin
                        help_button.setGeometry(x, y, button_size, button_size)
                        help_button.raise_()
                    
                    position_help_button()
                    
                    original_resize_event = getattr(form_widget, 'resizeEvent', None)
                    def new_resize_event(event):
                        if original_resize_event:
                            original_resize_event(event)
                        position_help_button()
                    
                    form_widget.resizeEvent = new_resize_event
                    form_widget._help_button = help_button
                
            return True
    except Exception as e:
        logger.debug(f"Help-Integration für {form_name} fehlgeschlagen: {e}")
    return False


if __name__ == '__main__':
    print(time_to_string(datetime.datetime.now().time()))
