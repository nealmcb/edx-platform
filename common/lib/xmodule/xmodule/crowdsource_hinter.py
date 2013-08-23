"""
Adds crowdsourced hinting functionality to lon-capa numerical response problems.

Currently experimental - not for instructor use, yet.
"""

import logging
import json
import random
import copy

from pkg_resources import resource_string

from lxml import etree

from xmodule.x_module import XModule
from xmodule.capa_module import CapaModule
from xmodule.raw_module import RawDescriptor
from xblock.core import Scope, String, Integer, Boolean, Dict, List
from xmodule.modulestore import Location
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import InvalidLocationError

from capa.responsetypes import FormulaResponse

from django.utils.html import escape
from django.conf import settings

log = logging.getLogger(__name__)

# A global variable that tracks what problems can have hinting.
problem_choices = []


def get_problem_choices():
    global problem_choices
    return problem_choices


class CrowdsourceHinterFields(object):
    """Defines fields for the crowdsource hinter module."""
    has_children = True

    display_name = String(scope=Scope.settings, default='Crowdsourced Hinter')
    target_problem = String(help='The id of the problem we are hinting for.', scope=Scope.settings,
                            default='', values=get_problem_choices)
    moderate = String(help='String "True"/"False" - activates moderation', scope=Scope.settings,
                      default='False')
    debug = String(help='String "True"/"False" - allows multiple voting', scope=Scope.settings,
                   default='False')
    # Usage: hints[answer] = {str(pk): [hint_text, #votes]}
    # hints is a dictionary that takes answer keys.
    # Each value is itself a dictionary, accepting hint_pk strings as keys,
    # and returning [hint text, #votes] pairs as values
    hints = Dict(help='A dictionary containing all the active hints.', scope=Scope.content, default={})
    mod_queue = Dict(help='A dictionary containing hints still awaiting approval', scope=Scope.content,
                     default={})
    hint_pk = Integer(help='Used to index hints.', scope=Scope.content, default=0)

    # A list of previous hints that a student viewed.
    # Of the form [answer, [hint_pk_1, ...]] for each problem.
    # Sorry about the variable name - I know it's confusing.
    previous_answers = List(help='A list of hints viewed.', scope=Scope.user_state, default=[])

    # user_submissions actually contains a list of previous answers submitted.
    # (Originally, preivous_answers did this job, hence the name confusion.)
    user_submissions = List(help='A list of previous submissions', scope=Scope.user_state, default=[])
    user_voted = Boolean(help='Specifies if the user has voted on this problem or not.',
                         scope=Scope.user_state, default=False)


class CrowdsourceHinterModule(CrowdsourceHinterFields, XModule):
    """
    An Xmodule that makes crowdsourced hints.
    Currently, only works on capa problems with exactly one numerical response,
    and no other parts.

    Example usage:
    <crowdsource_hinter target_problem="i4x://my/problem/location">
        <problem blah blah />
    </crowdsource_hinter>

    XML attributes:
    -moderate="True" will not display hints until staff approve them in the hint manager.
    -debug="True" will let users vote as often as they want.
    """
    icon_class = 'crowdsource_hinter'
    css = {'scss': [resource_string(__name__, 'css/crowdsource_hinter/display.scss')]}
    js = {'coffee': [resource_string(__name__, 'js/src/crowdsource_hinter/display.coffee')],
          'js': []}
    js_module_name = "Hinter"

    def __init__(self, *args, **kwargs):
        XModule.__init__(self, *args, **kwargs)
        self.init_error = None

        # Determine whether we are in Studio.  In Studio, accessing self.hints raises
        # an exception.
        self.in_studio = False
        try:
            self.hints
        except TypeError:
            self.in_studio = True
            self.setup_studio()

        # Get the problem we are hinting for.
        try:
            problem_loc = Location(self.target_problem)
        except InvalidLocationError:
            # This means the location wasn't chosen at all.
            self.init_error = '''Choose a target problem under Edit -> Settings.  Hinting will
                be enabled on the first response blank of the problem you choose.  Right now,
                hinting only works on numerical and formula response blanks.'''
            return
        problem_descriptors = modulestore().get_items(problem_loc)
        try:
            self.problem_module = self.system.get_module(problem_descriptors[0])
        except IndexError:
            self.init_error = 'The problem you specified could not be found!'
            return

        # Find the responder for this problem,
        try:
            responder = self.problem_module.lcp.responders.values()[0]
        except IndexError:
            self.init_error = 'The problem you specified does not have any response blanks!'
            return

        # We need to know whether we are working with a FormulaResponse problem.
        self.is_formula = isinstance(self, FormulaResponse)
        if self.is_formula:
            self.answer_to_str = self.formula_answer_to_str
        else:
            self.answer_to_str = self.numerical_answer_to_str
        # compare_answer is expected to return whether its two inputs are close enough
        # to be equal, or raise a StudentInputError if one of the inputs is malformatted.
        if hasattr(responder, 'compare_answer') and hasattr(responder, 'validate_answer'):
            self.compare_answer = responder.compare_answer
            self.validate_answer = responder.validate_answer
        else:
            # This response type is not supported!
            self.init_error = 'Response type not supported for hinting.'
            log.exception(self.init_error)

    def get_html(self):
        """
        Puts a wrapper around the problem html.  This wrapper includes ajax urls of the
        hinter and of the problem.
        - Dependent on lon-capa problem.
        """
        # Display any errors generated in __init__.  This is mostly for instructors to
        # see in Studio.
        if self.init_error is not None:
            return unicode(self.init_error)

        if self.in_studio:
            # We're in studio mode.

            # Take the entire url
            # - minus the last two segments
            # - minus the i4x
            # - append /courseware/hint_manager
            # - prepend LMS_BASE/courses/
            # Ex: i4x://Me/19.001/crowdsource_hinter/ec4d140d58114daeabb6f1819547decf@draft
            # -> localhost:8000/courses/Me/19.001/courseware/hint_manager
            manager_url = settings.LMS_BASE + '/courses' +\
                '/'.join(self.location.url().split('/')[1:-2]) + '/courseware/hint_manager'
            return '''This is a crowdsourced hinting module for {name}.  This message is only
                visible in Studio - your students will see the actual hinting module.
                <br /><br />
                To add or moderate hints, visit <a href="{manager_url}">{manager_url}</a>'''.format(
                    name=self.problem_module.display_name_with_default,
                    manager_url=manager_url,
                )
        else:
            if self.debug == 'True':
                # Reset the user vote, for debugging only!
                self.user_voted = False
            if self.hints == {}:
                # Force self.hints to be written into the database.  (When an xmodule is initialized,
                # fields are not added to the db until explicitly changed at least once.)
                self.hints = {}

        # The event listener uses the ajax url to find the child.
        child_url = self.problem_module.system.ajax_url

        # Return a little section for displaying hints.
        out = '<section class="crowdsource-wrapper" data-url="' + self.system.ajax_url +\
            '" data-child-url = "' + child_url + '"> </section>'

        return out

    def setup_studio(self):
        global problem_choices
        """
        Create a list of problems within this section, to offer as choices for the
        target problem.
        Updates a global variable; does not return anything.
        """
        # problem_choies contains dictionaries of {'display_name': readable name,
        # 'value': system name}, each representing a choice.
        # The choices should be all problems in the same section as this hinter
        # module.
        problem_choices = []
        # Find the parent of this module.
        # This is sort of clunky - we have to loop through all modules.
        all_modules = modulestore().get_items(Location(course=self.location.course, revision='draft'))
        parent = None
        for candidate_parent in all_modules:
            for child in candidate_parent.get_children():
                if self.descriptor.location == child.location:
                    parent = candidate_parent
                    break
            if parent is not None:
                break

        # Add all problems that are children of our parent.
        for descriptor in parent.get_children():
            if descriptor.module_class == CapaModule:
                problem_choices.append({'display_name': descriptor.display_name_with_default,
                                        'value': str(descriptor.location)})

    def numerical_answer_to_str(self, answer):
        """
        Converts capa numerical answer format to a string representation
        of the answer.
        -Lon-capa dependent.
        -Assumes that the problem only has one part.
        """
        return str(answer.values()[0])

    def formula_answer_to_str(self, answer):
        """
        Converts capa formula answer into a string.
        -Lon-capa dependent.
        -Assumes that the problem only has one part.
        """
        return str(answer.values()[0])

    def get_matching_answers(self, answer):
        """
        Look in self.hints, and find all answer keys that are "equal with tolerance"
        to the input answer.
        """
        return [key for key in self.hints if self.compare_answer(key, answer)]

    def handle_ajax(self, dispatch, data):
        """
        This is the landing method for AJAX calls.
        """
        if dispatch == 'get_hint':
            out = self.get_hint(data)
        elif dispatch == 'get_feedback':
            out = self.get_feedback(data)
        elif dispatch == 'vote':
            out = self.tally_vote(data)
        elif dispatch == 'submit_hint':
            out = self.submit_hint(data)
        else:
            return json.dumps({'contents': 'Error - invalid operation.'})

        if out is None:
            out = {'op': 'empty'}
        elif 'error' in out:
            # Error in processing.
            out.update({'op': 'error'})
        else:
            out.update({'op': dispatch})
        return json.dumps({'contents': self.system.render_template('hinter_display.html', out)})

    def get_hint(self, data):
        """
        The student got the incorrect answer found in data.  Give him a hint.

        Called by hinter javascript after a problem is graded as incorrect.
        Args:
        `data` -- must be interpretable by answer_to_str.
        Output keys:
            - 'hints' is a list of hint strings to show to the user.
            - 'answer' is the parsed answer that was submitted.
        Will record the user's wrong answer in user_submissions, and the hints shown
        in previous_answers.
        """
        # First, validate our inputs.
        try:
            answer = self.answer_to_str(data)
        except (ValueError, AttributeError):
            # Sometimes, we get an answer that's just not parsable.  Do nothing.
            log.exception('Answer not parsable: ' + str(data))
            return
        if not self.validate_answer(answer):
            # Answer is not in the right form.
            log.exception('Answer not valid: ' + str(answer))
            return
        if answer not in self.user_submissions:
            self.user_submissions += [answer]

        # For all answers similar enough to our own, accumulate all hints together.
        # Also track the original answer of each hint.
        matching_answers = self.get_matching_answers(answer)
        matching_hints = {}
        for matching_answer in matching_answers:
            temp_dict = copy.deepcopy(self.hints[matching_answer])
            for key, value in temp_dict.items():
                # Each value now has hint, votes, matching_answer.
                temp_dict[key] = value + [matching_answer]
            matching_hints.update(temp_dict)
        # matching_hints now maps pk's to lists of [hint, votes, matching_answer]

        # Finally, randomly choose a subset of matching_hints to actually show.
        if not matching_hints:
            # No hints to give.  Return.
            return
        # Get the top hint, plus two random hints.
        n_hints = len(matching_hints)
        hints = []
        # max(dict) returns the maximum key in dict.
        # The key function takes each pk, and returns the number of votes for the
        # hint with that pk.
        best_hint_index = max(matching_hints, key=lambda pk: matching_hints[pk][1])
        hints.append(matching_hints[best_hint_index][0])
        best_hint_answer = matching_hints[best_hint_index][2]
        # The brackets surrounding the index are for backwards compatability purposes.
        # (It used to be that each answer was paired with multiple hints in a list.)
        self.previous_answers += [[best_hint_answer, [best_hint_index]]]
        for i in xrange(min(2, n_hints - 1)):
            # Keep making random hints until we hit a target, or run out.
            while True:
                # random.choice randomly chooses an element from its input list.
                # (We then unpack the item, in this case data for a hint.)
                (hint_index, (rand_hint, votes, hint_answer)) =\
                    random.choice(matching_hints.items())
                if rand_hint not in hints:
                    break
            hints.append(rand_hint)
            self.previous_answers += [[hint_answer, [hint_index]]]
        return {'hints': hints,
                'answer': answer}

    def get_feedback(self, data):
        """
        The student got it correct.  Ask him to vote on hints, or submit a hint.

        Args:
        `data` -- not actually used.  (It is assumed that the answer is correct.)
        Output keys:
            - 'answer_to_hints': a nested dictionary.
              answer_to_hints[answer][hint_pk] returns the text of the hint.
            - 'user_submissions': the same thing as self.user_submissions.  A list of
              the answers that the user previously submitted.
        """
        # The student got it right.
        # Did he submit at least one wrong answer?
        if len(self.user_submissions) == 0:
            # No.  Nothing to do here.
            return
        # Make a hint-voting interface for each wrong answer.  The student will only
        # be allowed to make one vote / submission, but he can choose which wrong answer
        # he wants to look at.
        answer_to_hints = {}    # answer_to_hints[answer text][hint pk] -> hint text

        # Go through each previous answer, and populate index_to_hints and index_to_answer.
        for i in xrange(len(self.previous_answers)):
            answer, hints_offered = self.previous_answers[i]
            if answer not in answer_to_hints:
                answer_to_hints[answer] = {}
            if answer in self.hints:
                # Go through each hint, and add to index_to_hints
                for hint_id in hints_offered:
                    if (hint_id is not None) and (hint_id not in answer_to_hints[answer]):
                        try:
                            answer_to_hints[answer][hint_id] = self.hints[answer][str(hint_id)][0]
                        except KeyError:
                            # Sometimes, the hint that a user saw will have been deleted by the instructor.
                            continue
        return {'answer_to_hints': answer_to_hints,
                'user_submissions': self.user_submissions}

    def tally_vote(self, data):
        """
        Tally a user's vote on his favorite hint.

        Args:
        `data` -- expected to have the following keys:
            'answer': text of answer we're voting on
            'hint': hint_pk
            'pk_list': A list of [answer, pk] pairs, each of which representing a hint.
                       We will return a list of how many votes each hint in the list has so far.
                       It's up to the browser to specify which hints to return vote counts for.

        Returns key 'hint_and_votes', a list of (hint_text, #votes) pairs.
        """
        if self.user_voted:
            return {'error': 'Sorry, but you have already voted!'}
        ans = data['answer']
        if not self.validate_answer(ans):
            # Uh oh.  Invalid answer.
            log.exception('Failure in hinter tally_vote: Unable to parse answer: {ans}'.format(ans=ans))
            return {'error': 'Failure in voting!'}
        hint_pk = str(data['hint'])
        # We use temp_dict because we need to do a direct write for the database to update.
        temp_dict = self.hints
        try:
            temp_dict[ans][hint_pk][1] += 1
        except KeyError:
            log.exception('''Failure in hinter tally_vote: User voted for non-existant hint:
                             Answer={ans} pk={hint_pk}'''.format(ans=ans, hint_pk=hint_pk))
            return {'error': 'Failure in voting!'}
        self.hints = temp_dict
        # Don't let the user vote again!
        self.user_voted = True

        # Return a list of how many votes each hint got.
        pk_list = json.loads(data['pk_list'])
        hint_and_votes = []
        for answer, vote_pk in pk_list:
            if not self.validate_answer(answer):
                log.exception('In hinter tally_vote, couldn\'t parse {ans}'.format(ans=answer))
                continue
            try:
                hint_and_votes.append(temp_dict[answer][str(vote_pk)])
            except KeyError:
                log.exception('In hinter tally_vote, couldn\'t find: {ans}, {vote_pk}'.format(
                              ans=answer, vote_pk=str(vote_pk)))

        hint_and_votes.sort(key=lambda pair: pair[1], reverse=True)
        # Reset self.previous_answers and user_submissions.
        self.previous_answers = []
        self.user_submissions = []
        return {'hint_and_votes': hint_and_votes}

    def submit_hint(self, data):
        """
        Take a hint submission and add it to the database.

        Args:
        `data` -- expected to have the following keys:
            'answer': text of answer
            'hint': text of the new hint that the user is adding
        Returns a thank-you message.
        """
        # Do html escaping.  Perhaps in the future do profanity filtering, etc. as well.
        hint = escape(data['hint'])
        answer = data['answer']
        if not self.validate_answer(answer):
            log.exception('Failure in hinter submit_hint: Unable to parse answer: {ans}'.format(
                          ans=answer))
            return {'error': 'Could not submit answer'}
        # Only allow a student to vote or submit a hint once.
        if self.user_voted:
            return {'message': 'Sorry, but you have already voted!'}
        # Add the new hint to self.hints or self.mod_queue.  (Awkward because a direct write
        # is necessary.)
        if self.moderate == 'True':
            temp_dict = self.mod_queue
        else:
            temp_dict = self.hints
        if answer in temp_dict:
            temp_dict[answer][str(self.hint_pk)] = [hint, 1]     # With one vote (the user himself).
        else:
            temp_dict[answer] = {str(self.hint_pk): [hint, 1]}
        self.hint_pk += 1
        if self.moderate == 'True':
            self.mod_queue = temp_dict
        else:
            self.hints = temp_dict
        # Mark the user has having voted; reset previous_answers
        self.user_voted = True
        self.previous_answers = []
        self.user_submissions = []
        return {'message': 'Thank you for your hint!'}


class CrowdsourceHinterDescriptor(CrowdsourceHinterFields, RawDescriptor):
    module_class = CrowdsourceHinterModule
    stores_state = True

    @classmethod
    def definition_from_xml(cls, xml_object, system):
        children = []
        for child in xml_object:
            try:
                children.append(system.process_xml(etree.tostring(child, encoding='unicode')).location.url())
            except Exception as e:
                log.exception("Unable to load child when parsing CrowdsourceHinter. Continuing...")
                if system.error_tracker is not None:
                    system.error_tracker("ERROR: " + str(e))
                continue
        return {}, children

    def definition_to_xml(self, resource_fs):
        xml_object = etree.Element('crowdsource_hinter')
        for child in self.get_children():
            xml_object.append(
                etree.fromstring(child.export_to_xml(resource_fs)))
        return xml_object
