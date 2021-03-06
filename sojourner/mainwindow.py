# vim: set fileencoding=utf-8 sts=4 sw=4 :
import sys
import gtk
import gio
import pango
import ConfigParser
import hildon
from sojourner import VERSION
from sojourner.malvern import *
from sojourner.updater import Updater
from sojourner.schedule import Schedule, MalformedSchedule, Event
from sojourner.eventlist import EventList
from sojourner.categorylist import CategoryList
from sojourner.conference import Conference

class MainWindow(MaybeStackableWindow):
    def fetched_schedule_cb(self, updater, schedule, exc):
        updater.destroy()

        if schedule is not None:
            self.schedule = schedule

            # Hooray! We can now let the user interact with the application, if
            # they weren't already.
            for b in self.buttons:
                b.set_sensitive(True)
        else:
            print repr(exc)
            
            if isinstance(exc, MalformedSchedule):
                hildon.hildon_banner_show_information(self, '', 'Schedule file was malformed')
            else:
                hildon.hildon_banner_show_information(self, '', 'Error downloading schedule')

    def _on_orientation_changed(self, is_portrait):
        if is_portrait:
            self.views.set_current_page(1)
        else:
            self.views.set_current_page(0)

    def _make_button_grid(self, portrait):
        # Hi. My name's Will, and I'm a functional programming addict.
        def _make_button(label, on_activated, icon=None):
            b = MagicButton(label, icon, thumb_height=True)
            b.connect('clicked', on_activated)
            self.buttons.add(b)
            return b

        buttons = [ _make_button(*x) for x in [
            ("All events", lambda b:
                EventList(self.schedule, "All events", self.schedule.events)),
            ("Events by room", lambda b: CategoryList(self.schedule, "Rooms",
                self.schedule.events_by_room, Event.OMIT_ROOM)),
            ("Events by track", lambda b: CategoryList(self.schedule, "Tracks",
                self.schedule.events_by_track, Event.OMIT_TRACK,
                show_swatches=True)),
            ("Favourites", lambda b: EventList(self.schedule, "Favourites",
                self.schedule.favourites), STAR_ICON),
        ]]

        if portrait:
            rows=4
            columns=1
        else:
            rows=2
            columns=2

        coordinates = [ (x, y) for x in range(0, columns)
                               for y in range(0, rows)
                      ]

        table = gtk.Table(rows=rows, columns=columns, homogeneous=True)
        table.set_row_spacings(6)
        table.set_col_spacings(6)

        for ((x, y), button) in zip(coordinates, buttons):
            table.attach(button, x, x + 1, y, y + 1)

        vbox = gtk.VBox(spacing=0)

        banner = gtk.image_new_from_file(self.__conference.get_banner())
        vbox.pack_start(banner, expand=True)

        vbox.pack_end(table, expand=False)

        return vbox

    def run_updater(self):
        updater = Updater(self,
            self.__conference.get_schedule_url(),
            self.schedule_file, self.fetched_schedule_cb)
        updater.show_all()

    def make_menu(self):
        menu = AppMenu()

        button = gtk.Button("Refresh schedule")
        button.connect('clicked', lambda button: self.run_updater())
        menu.append(button)

        menu.show_all()
        self.set_app_menu(menu)

    def __init__(self):
        MaybeStackableWindow.__init__(self, "Sojourner",
            orientation_changed_cb=self._on_orientation_changed)
        self.connect("delete_event", gtk.main_quit, None)

        # For Sojourner config file
        self.__config = ConfigParser.RawConfigParser()

        # Find out the currently active conference from the config file

        self.__config.read(sojourner_data_path('sojourner'))
        current_conference = self.__config.get('sojourner', 'current_conference')
        print "mainwindow.py: Setting current conference to %s" % current_conference
        # For the config file of the currently active conference
        self.__conference = Conference(current_conference)

        # We use a notebook with no tabs and two pages to flip between
        # landscape and portrait layouts as necessary. We'll find out shortly
        # which way up we actually are, when self._on_orientation_changed is
        # called for the initial configure event, and select the right tab.
        self.views = gtk.Notebook()
        self.views.set_show_tabs(False)
        self.views.set_show_border(False)
        self.buttons = set()
        self.views.append_page(self._make_button_grid(portrait=False))
        self.views.append_page(self._make_button_grid(portrait=True))
        self.add_with_margins(self.views)
        self.show_all()

        self.make_menu()

        if have_hildon:
            sojourner.portrait.FremantleRotation("sojourner", self,
                version=VERSION)

        self.schedule_file = config_file(self.__conference.get_cached_xml())

        try:
            # FIXME: if we have a schedule but no pickle file, this takes ages
            # and makes the app seem to take forever to start. We could run
            # this in a thread. But the updater does do this in a thread; so at
            # worst if the user somehow ends up with the schedule XML but no
            # pickle file the UI will block once, the next time they start the
            # app.
            self.schedule = Schedule(self.schedule_file.get_path())
        except Exception, e:
            # Stop the user from interacting with the application until we have
            # a schedule.
            for b in self.buttons:
                b.set_sensitive(False)

            self.run_updater()
