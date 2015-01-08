# vim: set fileencoding=utf-8 sts=4 sw=4 :

import xml.dom.minidom as minidom
from xml.dom.minidom import Node
from xml.parsers.expat import ExpatError
import datetime as dt
import cPickle
import os.path

import colorsys
import hashlib
import gtk

import re

from sojourner.malvern import config_file, esc

def getChildrenByTagName(node, name):
    """Similar to node.getElementsByTagName(name), but only fetches immediate
    children."""
    return [child for child in node.childNodes if child.nodeName == name]

def get_text(node, strip_newlines=False):
    """Concatenates all of node's text children, optionally removing single
    newlines (but preserving paragraphs)."""
    text = ''.join([child.data for child in node.childNodes
                               if child.nodeType == Node.TEXT_NODE])
    if strip_newlines:
        # The schedule has a bunch of places which do this:
        #   "paragraph one\n\nparagraph two"
        # and some that do this:
        #   "paragraph one\n \nparagraph two"
        # This is tediously ad-hoc, and a real Markdown parser would be better.
        tidier_double_newlines = '\n'.join(text.split(' \n'))
        text = '\n\n'.join(
            [p.replace('\n', ' ')
                for p in tidier_double_newlines.split('\n\n')])

    return text.lstrip().rstrip()

def get_time_delta(node):
    (h, m) = get_text(node).split(':')
    return dt.timedelta(hours=int(h), minutes=int(m))

def get_text_from_children(parent, name, joiner=''):
    """Given a node, returns the text contents of all its children named
    'name', joined by 'joiner'. For example, given a node 'foo' representing
    this stanza:

        <foo>
          <bar>hello</bar>
          <baz>not this one</baz>
          <bar>world</bar>
        <foo>

    then:

        >>> get_text_from_children(foo, 'bar', joiner=' ')
        u'hello world'.
    """

    texts = [get_text(c) for c in getChildrenByTagName(parent, name)]
    return joiner.join(texts)

def by_start_time(x, y):
    # FIXME: should this be Event.__cmp__?
    return cmp(x.start, y.start)

class MalformedSchedule(Exception):
    pass

# We deliberately stash the track colours outside of any object.  There's no
# need to pickle these: they're based on the track name, so are stable.
swatches = {}

def get_color(track):
    if track in swatches:
        # In Violet
        return swatches[track]
    else:
        # We pick nicely matching colours by fixing S and V and varying H. The
        # first byte of an md5sum will do nicely for picking H!
        m = hashlib.md5()
        m.update(track)
        h = ord(m.digest()[0]) / 255.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.9, 0.9)
        swatch = gtk.gdk.Color(int(r * 65535), int(g * 65535), int(b * 65535))
        swatches[track] = swatch
        return swatch

class Schedule(object):
    """Version number for pickled event data. This must be incremented if this
    class, or Event, is modified."""
    __VERSION = 8

    def __init__(self, schedule_path):
        self.schedule_path = schedule_path

        (self.events, self.events_by_id, self.events_by_room,
            self.events_by_track) = self.__load_schedule()

        self.favourites = self.__load_favourites()

    def __load_schedule(self):
        """Tries to load the schedule from a pre-parsed pickle file; if that
        doesn't fly, reads the actual XML and pickles the result for later."""
        pickle_path = self.schedule_path + '.pickle'

        try:
            if os.path.getmtime(pickle_path) <= \
                    os.path.getmtime(self.schedule_path):
                raise Exception('pickle is out of date')

            version, stuff = cPickle.load(open(pickle_path, 'rb'))

            if version != Schedule.__VERSION:
                raise Exception('expected version %u, got version %u' %
                    (Schedule.__VERSION, version))

            return stuff
        except Exception, e:
            stuff = self.__parse_schedule()

            try:
                cPickle.dump((Schedule.__VERSION, stuff),
                    open(pickle_path, 'wb'),
                    protocol=2)
            except Exception, e:
                print "Couldn't pickle schedule: %s" % e

            return stuff

    def __parse_schedule(self):
        try:
            doc = minidom.parse(self.schedule_path)
        except ExpatError, e:
            raise MalformedSchedule(e)

        schedule_elt = doc.documentElement

        if doc.documentElement.nodeName != 'schedule':
            raise MalformedSchedule('Root element was <%s/>, not <schedule/>' %
                doc.documentElement.nodeName)

        events = []
        events_by_id = {}
        events_by_room = {}
        events_by_track = {}

        for day in getChildrenByTagName(doc.documentElement, 'day'):
            date = dt.datetime.strptime(day.getAttribute('date'), '%Y-%m-%d')

            for room_node in getChildrenByTagName(day, 'room'):
                room = room_node.getAttribute('name')

                for node in getChildrenByTagName(room_node, 'event'):
                    e = Event(node, date, room)
                    events.append(e)
                    events_by_id[e.id] = e

                    blah = events_by_room.get(e.room, [])
                    blah.append(e)
                    events_by_room[e.room] = blah

                    blah = events_by_track.get(e.track, [])
                    blah.append(e)
                    events_by_track[e.track] = blah

        events.sort(cmp=by_start_time)

        return (events, events_by_id, events_by_room, events_by_track)

    def __load_favourites(self):
        favourites = []

        try:
            f = file(self._favourites_file(), 'r')
            for id in f.readlines():
                event = self.events_by_id[id.strip()]

                if event not in favourites:
                    favourites.append(event)
            f.close()
        except IOError:
            # I guess they don't have any favourites
            pass

        return favourites

    def _favourites_file(self):
        return os.path.dirname(self.schedule_path) + '/favourites'

    def _write_favourites(self):
        f = file(self._favourites_file(), 'w')
        for fav in self.favourites:
            f.write("%s\n" % fav.id)
        f.close()

    def add_favourite(self, event):
        if not event in self.favourites:
            self.favourites.append(event)
            self.favourites.sort(cmp=by_start_time)
            self._write_favourites()

    def remove_favourite(self, event):
        try:
            self.favourites.remove(event)
            self._write_favourites()
        except ValueError, e:
            # Oops! I guess 'event' wasn't in the favourites.
            print e

class Event(object):
    def __init__(self, node, date, room):
        self.id = node.getAttribute('id')
        self.room = room

        children = [ c for c in node.childNodes
                       if c.nodeType == Node.ELEMENT_NODE
                   ]
        for child in children:
            n = child.nodeName

            if n == 'title':
                self.title = get_text(child)
            elif n == 'start':
                self.start = date + get_time_delta(child)
            elif n == 'duration':
                self.duration = get_time_delta(child)
            elif n == 'track':
                self.track = get_text(child)

            # In practice, abstract and description are the only places that
            # stray newlines show up. FIXME: I think they're actually in
            # Markdown format, maybe we could use Python-Markdown to do better
            # than this?
            elif n == 'abstract':
                self.abstract = get_text(child, strip_newlines=True)
            elif n == 'description':
                self.description = get_text(child, strip_newlines=True)
            elif n == 'persons':
                # FIXME: maybe joining the people together should be up to the
                # widgets?
                self.person = get_text_from_children(child, 'person',
                    joiner=', ')
            else:
                pass

        self.end = self.start + self.duration

        # These are not methods because strftime showed up surprisingly high on
        # the profile. They're localized; I'm not sure if this is a good thing.
        self.day_name = self.start.strftime("%A")
        self.start_str = self.start.strftime('%H:%M')
        self.end_str = self.end.strftime('%H:%M')

        # And these are pre-computed because they were about a quarter of
        # showing the full list.
        bg = get_color(self.track)
        if bg.red + bg.green + bg.blue > (65535 * 3 / 2):
            fg = '#000000'
        else:
            fg = '#ffffff'

        self.bg = bg

        summary_data = {
            'title': esc(self.title),
            'speaker': esc(self.person),
            'day': self.day_name,
            'start': self.start_str,
            'end': self.end_str,
            'room': esc(self.room),
            'track': esc(self.track),
            'track_background': bg.to_string(),
            'track_foreground': fg
        }

        self.full_summary = Event.FULL_SUMMARY_FORMAT % summary_data
        self.summary_sans_day = Event.OMIT_DAY_FORMAT % summary_data
        self.summary_sans_room = Event.OMIT_ROOM_FORMAT % summary_data
        self.summary_sans_track = Event.OMIT_TRACK_FORMAT % summary_data

    FULL_SUMMARY_FORMAT = """<b>%(title)s</b>
<small>%(speaker)s <i>(%(day)s %(start)s–%(end)s, %(room)s, <span background='%(track_background)s' foreground='%(track_foreground)s'>%(track)s</span>)</i></small>"""

    OMIT_DAY_FORMAT = """<b>%(title)s</b>
<small>%(speaker)s <i>(%(start)s–%(end)s, %(room)s, %(track)s)</i></small>"""

    OMIT_ROOM_FORMAT = """<b>%(title)s</b>
<small>%(speaker)s <i>(%(start)s–%(end)s, %(track)s)</i></small>"""

    OMIT_TRACK_FORMAT = """<b>%(title)s</b>
<small>%(speaker)s <i>(%(start)s–%(end)s, %(room)s)</i></small>"""

    OMIT_NOTHING = 0
    OMIT_DAY = 1
    OMIT_ROOM = 2
    OMIT_TRACK = 3

    def summary(self, omit=OMIT_NOTHING):
        if omit == Event.OMIT_NOTHING:
            return self.full_summary
        elif omit == Event.OMIT_DAY:
            return self.summary_sans_day
        elif omit == Event.OMIT_ROOM:
            return self.summary_sans_room
        elif omit == Event.OMIT_TRACK:
            return self.summary_sans_track

    def full(self):
        if self.description.startswith(self.abstract):
            desc = self.description[len(self.abstract):]
        else:
            desc = self.description

        if desc == '':
            return "%s\n\n%s" % (self.full_summary, strip_tags(self.abstract))
        elif self.abstract == '':
            return "%s\n\n%s" % (self.full_summary, strip_tags(desc))
        else:
            return "%s\n\n%s\n\n%s" \
                % (self.full_summary, strip_tags(self.abstract), strip_tags(desc))

    def conflicts(self, other_event):
        if other_event == self:
            return False
        return not (self.start <= other_event.start and \
                    self.end <= other_event.start or \
                    self.start >= other_event.end)

def strip_tags(text):
    # Strip HTML tags
    # TODO: regular expressions shouldn't be used for this
    text = re.sub(r'<(/)?[a-z]+[0-9]*>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = esc(text)
    return text

