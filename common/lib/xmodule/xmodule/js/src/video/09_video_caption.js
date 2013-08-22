(function (requirejs, require, define) {

// VideoCaption module.
define(
'video/09_video_caption.js',
[],
function () {

    // VideoCaption() function - what this module "exports".
    return function (state) {
        state.videoCaption = {};

        _makeFunctionsPublic(state);

        // Depending on whether captions file could be loaded, the following
        // function invocation can succeed or fail. If it fails, we do not
        // go on with binding handlers to events.
        if (!state.videoCaption.renderElements()) {
            return;
        }

        state.videoCaption.bindHandlers();
    };

    // ***************************************************************
    // Private functions start here.
    // ***************************************************************

    // function _makeFunctionsPublic(state)
    //
    //     Functions which will be accessible via 'state' object. When called, these functions will
    //     get the 'state' object as a context.
    function _makeFunctionsPublic(state) {
        state.videoCaption.autoShowCaptions    = _.bind(autoShowCaptions, state);
        state.videoCaption.autoHideCaptions    = _.bind(autoHideCaptions, state);
        state.videoCaption.resize              = _.bind(resize, state);
        state.videoCaption.toggle              = _.bind(toggle, state);
        state.videoCaption.onMouseEnter        = _.bind(onMouseEnter, state);
        state.videoCaption.onMouseLeave        = _.bind(onMouseLeave, state);
        state.videoCaption.onMovement          = _.bind(onMovement, state);
        state.videoCaption.renderCaption       = _.bind(renderCaption, state);
        state.videoCaption.captionHeight       = _.bind(captionHeight, state);
        state.videoCaption.topSpacingHeight    = _.bind(topSpacingHeight, state);
        state.videoCaption.bottomSpacingHeight = _.bind(bottomSpacingHeight, state);
        state.videoCaption.scrollCaption       = _.bind(scrollCaption, state);
        state.videoCaption.search              = _.bind(search, state);
        state.videoCaption.play                = _.bind(play, state);
        state.videoCaption.pause               = _.bind(pause, state);
        state.videoCaption.seekPlayer          = _.bind(seekPlayer, state);
        state.videoCaption.hideCaptions        = _.bind(hideCaptions, state);
        state.videoCaption.calculateOffset     = _.bind(calculateOffset, state);
        state.videoCaption.updatePlayTime      = _.bind(updatePlayTime, state);
        state.videoCaption.setSubtitlesHeight  = _.bind(setSubtitlesHeight, state);

        state.videoCaption.renderElements      = _.bind(renderElements, state);
        state.videoCaption.bindHandlers        = _.bind(bindHandlers, state);
        state.videoCaption.fetchCaption        = _.bind(fetchCaption, state);
        state.videoCaption.captionURL          = _.bind(captionURL, state);
    }

    // ***************************************************************
    // Public functions start here.
    // These are available via the 'state' object. Their context ('this' keyword) is the 'state' object.
    // The magic private function that makes them available and sets up their context is makeFunctionsPublic().
    // ***************************************************************

    // function renderElements()
    //
    //     Create any necessary DOM elements, attach them, and set their initial configuration. Also
    //     make the created DOM elements available via the 'state' object. Much easier to work this
    //     way - you don't have to do repeated jQuery element selects.
    function renderElements() {
        this.videoCaption.loaded = false;

        this.videoCaption.subtitlesEl = this.el.find('ol.subtitles');
        this.videoCaption.hideSubtitlesEl = this.el.find('a.hide-subtitles');

        this.el.find('.video-wrapper').after(this.videoCaption.subtitlesEl);
        this.el.find('.video-controls .secondary-controls').append(this.videoCaption.hideSubtitlesEl);

        // Fetch the captions file. If no file was specified, then we hide
        // the "CC" button, and exit from this module. No further caption
        // initialization will happen.
        if (!this.videoCaption.fetchCaption()) {
            this.videoCaption.hideSubtitlesEl.hide();

            // Abandon all further operations with captions panel.
            return false;
        }

        this.videoCaption.setSubtitlesHeight();

        if (this.videoType === 'html5') {
            this.videoCaption.fadeOutTimeout = this.config.fadeOutTimeout;

            this.videoCaption.subtitlesEl.addClass('html5');
            this.captionHideTimeout = setTimeout(this.videoCaption.autoHideCaptions, this.videoCaption.fadeOutTimeout);
        }

        return true;
    }

    // function bindHandlers()
    //
    //     Bind any necessary function callbacks to DOM events (click, mousemove, etc.).
    function bindHandlers() {
        $(window).bind('resize', this.videoCaption.resize);
        this.videoCaption.hideSubtitlesEl.on('click', this.videoCaption.toggle);

        this.videoCaption.subtitlesEl
            .on(
                'mouseenter',
                this.videoCaption.onMouseEnter
            ).on(
                'mouseleave',
                this.videoCaption.onMouseLeave
            ).on(
                'mousemove',
                this.videoCaption.onMovement
            ).on(
                'mousewheel',
                this.videoCaption.onMovement
            ).on(
                'DOMMouseScroll',
                this.videoCaption.onMovement
            );

        if (this.videoType === 'html5') {
            this.el.on('mousemove', this.videoCaption.autoShowCaptions);
            this.el.on('keydown', this.videoCaption.autoShowCaptions);

            // Moving slider on subtitles is not a mouse move,
            // but captions and controls should be showed.
            this.videoCaption.subtitlesEl.on('scroll', this.videoCaption.autoShowCaptions);
            this.videoCaption.subtitlesEl.on('scroll', this.videoControl.showControls);
        }
    }

    function fetchCaption() {
        var _this = this;

        this.videoCaption.hideCaptions(this.hide_captions);

        // Check whether the captions file was specified. This is the point
        // where we either stop with the caption panel (so that a white empty
        // panel to the right of the video will not be shown), or carry on
        // further.
        if (!this.youtubeId('1.0')) {
            return false;
        }

        $.ajaxWithPrefix({
            url: _this.videoCaption.captionURL(),
            notifyOnError: false,
            success: function(captions) {
                _this.videoCaption.captions = captions.text;
                _this.videoCaption.start = captions.start;
                _this.videoCaption.loaded = true;

                if (onTouchBasedDevice()) {
                    _this.videoCaption.subtitlesEl.find('li').html(
                        gettext(
                            'Caption will be displayed when ' +
                            'you start playing the video.'
                        )
                    );
                } else {
                    _this.videoCaption.renderCaption();
                }
            }
        });

        return true;
    }

    function captionURL() {
        return '' + this.config.caption_asset_path + this.youtubeId('1.0') + '.srt.sjson';
    }

    function autoShowCaptions(event) {
        if (!this.captionsShowLock) {
            if (!this.captionsHidden) {
                return;
            }

            this.captionsShowLock = true;

            if (this.captionState === 'invisible') {
                this.videoCaption.subtitlesEl.show();
                this.captionState = 'visible';
            } else if (this.captionState === 'hiding') {
                this.videoCaption.subtitlesEl.stop(true, false).css('opacity', 1).show();
                this.captionState = 'visible';
            } else if (this.captionState === 'visible') {
                clearTimeout(this.captionHideTimeout);
            }

            this.captionHideTimeout = setTimeout(this.videoCaption.autoHideCaptions, this.videoCaption.fadeOutTimeout);

            this.captionsShowLock = false;
        }
    }

    function autoHideCaptions() {
        var _this;

        this.captionHideTimeout = null;

        if (!this.captionsHidden) {
            return;
        }

        this.captionState = 'hiding';

        _this = this;

        this.videoCaption.subtitlesEl.fadeOut(this.videoCaption.fadeOutTimeout, function () {
            _this.captionState = 'invisible';
        });
    }

    function resize() {
        this.videoCaption.subtitlesEl
            .find('.spacing:first').height(this.videoCaption.topSpacingHeight())
            .find('.spacing:last').height(this.videoCaption.bottomSpacingHeight());

        this.videoCaption.scrollCaption();

        this.videoCaption.setSubtitlesHeight();
    }

    function onMouseEnter() {
        if (this.videoCaption.frozen) {
            clearTimeout(this.videoCaption.frozen);
        }

        this.videoCaption.frozen = setTimeout(this.videoCaption.onMouseLeave, 10000);
    }

    function onMouseLeave() {
        if (this.videoCaption.frozen) {
            clearTimeout(this.videoCaption.frozen);
        }

        this.videoCaption.frozen = null;

        if (this.videoCaption.playing) {
            this.videoCaption.scrollCaption();
        }
    }

    function onMovement() {
        this.videoCaption.onMouseEnter();
    }

    function renderCaption() {
        var container,
            _this = this;
        container = $('<ol>');

        $.each(this.videoCaption.captions, function(index, text) {
            var liEl = $('<li>');

            liEl.html(text);

            liEl.attr({
                'data-index': index,
                'data-start': _this.videoCaption.start[index]
            });

            container.append(liEl);
        });

        this.videoCaption.subtitlesEl.html(container.html());

        this.videoCaption.subtitlesEl.find('li[data-index]').on('click', this.videoCaption.seekPlayer);

        this.videoCaption.subtitlesEl.prepend($('<li class="spacing">').height(this.videoCaption.topSpacingHeight()));
        this.videoCaption.subtitlesEl.append($('<li class="spacing">').height(this.videoCaption.bottomSpacingHeight()));

        this.videoCaption.rendered = true;
    }

    function scrollCaption() {
        var el = this.videoCaption.subtitlesEl.find('.current:first');

        if (!this.videoCaption.frozen && el.length) {
            this.videoCaption.subtitlesEl.scrollTo(
                el,
                {
                    offset: -this.videoCaption.calculateOffset(el)
                }
            );
        }
    }

    function search(time) {
        var index, max, min;

        if (this.videoCaption.loaded) {
            min = 0;
            max = this.videoCaption.start.length - 1;

            while (min < max) {
                index = Math.ceil((max + min) / 2);

                if (time < this.videoCaption.start[index]) {
                    max = index - 1;
                }

                if (time >= this.videoCaption.start[index]) {
                    min = index;
                }
            }

            return min;
        }

        return undefined;
    }

    function play() {
        if (this.videoCaption.loaded) {
            if (!this.videoCaption.rendered) {
                this.videoCaption.renderCaption();
            }

            this.videoCaption.playing = true;
        }
    }

    function pause() {
        if (this.videoCaption.loaded) {
            this.videoCaption.playing = false;
        }
    }

    function updatePlayTime(time) {
        var newIndex;

        if (this.videoCaption.loaded) {
            // Current mode === 'flash' can only be for YouTube videos. So, we
            // don't have to also check for videoType === 'youtube'.
            if (this.currentPlayerMode === 'flash') {
                // Total play time changes with speed change. Also there is
                // a 250 ms delay we have to take into account.
                time = Math.round(
                    Time.convert(time, this.speed, '1.0') * 1000 + 250
                );
            } else {
                // Total play time remains constant when speed changes.
                time = Math.round(parseInt(time, 10) * 1000);
            }

            newIndex = this.videoCaption.search(time);

            if (
                newIndex !== void 0 &&
                this.videoCaption.currentIndex !== newIndex
            ) {
                if (this.videoCaption.currentIndex) {
                    this.videoCaption.subtitlesEl
                        .find('li.current')
                        .removeClass('current');
                }

                this.videoCaption.subtitlesEl
                    .find("li[data-index='" + newIndex + "']")
                    .addClass('current');

                this.videoCaption.currentIndex = newIndex;

                this.videoCaption.scrollCaption();
            }
        }
    }

    function seekPlayer(event) {
        var time;

        event.preventDefault();

        // Current mode === 'flash' can only be for YouTube videos. So, we
        // don't have to also check for videoType === 'youtube'.
        if (this.currentPlayerMode === 'flash') {
            // Total play time changes with speed change. Also there is
            // a 250 ms delay we have to take into account.
            time = Math.round(
                Time.convert(
                    $(event.target).data('start'), '1.0', this.speed
                ) / 1000
            );
        } else {
            // Total play time remains constant when speed changes.
            time = parseInt($(event.target).data('start'), 10)/1000;
        }

        this.trigger(
            'videoPlayer.onCaptionSeek',
            {
                'type': 'onCaptionSeek',
                'time': time
            }
        );
    }

    function calculateOffset(element) {
        return this.videoCaption.captionHeight() / 2 - element.height() / 2;
    }

    function topSpacingHeight() {
        return this.videoCaption.calculateOffset(this.videoCaption.subtitlesEl.find('li:not(.spacing):first'));
    }

    function bottomSpacingHeight() {
        return this.videoCaption.calculateOffset(this.videoCaption.subtitlesEl.find('li:not(.spacing):last'));
    }

    function toggle(event) {
        event.preventDefault();

        if (this.el.hasClass('closed')) {
            this.videoCaption.hideCaptions(false);
        } else {
            this.videoCaption.hideCaptions(true);
        }
    }

    function hideCaptions(hide_captions) {
        var type;

        if (hide_captions) {
            type = 'hide_transcript';
            this.captionsHidden = true;
            this.videoCaption.hideSubtitlesEl.attr('title', gettext('Turn on captions'));
            this.el.addClass('closed');
        } else {
            type = 'show_transcript';
            this.captionsHidden = false;
            this.videoCaption.hideSubtitlesEl.attr('title', gettext('Turn off captions'));
            this.el.removeClass('closed');
            this.videoCaption.scrollCaption();
        }

        if (this.videoPlayer) {
            this.videoPlayer.log(type, {
                currentTime: this.videoPlayer.currentTime
            });
        }

        this.videoCaption.setSubtitlesHeight();

        $.cookie('hide_captions', hide_captions, {
            expires: 3650,
            path: '/'
        });
    }

    function captionHeight() {
        if (this.isFullScreen) {
            return $(window).height() - this.el.find('.video-controls').height() -
                    0.5 * this.videoControl.sliderEl.height() -
                    2 * parseInt(this.videoCaption.subtitlesEl.css('padding-top'), 10);
        } else {
            return this.el.find('.video-wrapper').height();
        }
    }

    function setSubtitlesHeight() {
        var height = 0;
        if (this.videoType === 'html5'){
            // on page load captionHidden = undefined
            if  (
                (this.captionsHidden === undefined && this.hide_captions === true ) ||
                (this.captionsHidden === true) ) {
                // In case of html5 autoshowing subtitles,
                // we ajdust height of subs, by height of scrollbar
                height = this.videoControl.el.height() + 0.5 * this.videoControl.sliderEl.height();
                // height of videoControl does not contain height of slider.
                // (css is set to absolute, to avoid yanking when slider autochanges its height)
            }
        }
        this.videoCaption.subtitlesEl.css({
            maxHeight: this.videoCaption.captionHeight() - height
        });
     }
});

}(RequireJS.requirejs, RequireJS.require, RequireJS.define));
