#pylint: disable=C0111
#pylint: disable=W0621

from lettuce import world, step


@step('I click on View Courseware')
def i_click_on_view_courseware(step):
    world.css_click('a.enter-course')


@step('I click on the "([^"]*)" tab$')
def i_click_on_the_tab(step, tab_text):
    world.click_link(tab_text)


@step('I visit the courseware URL$')
def i_visit_the_course_info_url(step):
    world.visit('/courses/MITx/6.002x/2012_Fall/courseware')


@step(u'I am on the dashboard page$')
def i_am_on_the_dashboard_page(step):
    assert world.is_css_present('section.courses')
    assert world.url_equals('/dashboard')


@step('the "([^"]*)" tab is active$')
def the_tab_is_active(step, tab_text):
    assert world.css_text('.course-tabs a.active') == tab_text


@step('the login dialog is visible$')
def login_dialog_visible(step):
    assert world.css_visible('form#login_form.login_form')
