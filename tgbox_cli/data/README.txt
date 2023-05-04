[WHITE]TGBOX-CLI README[WHITE]
    Hi and Welcome to the short TGBOX-CLI README! This file
    intended to help you to get info about this program.

[BRIGHT_BLACK]What is a TGBOX?[BRIGHT_BLACK]
    TGBOX (TelegramBox) is a non-official API to the encrypted
    cloud storage around the Telegram messenger written on
    a Python programming language by me, author of this
    CLI app! In sake of a DRY principle we will not cover
    here API documentation. If you wonder what is a TGBOX
    in depth, then feel free to check the docs:
        [BLUE]tgbox.readthedocs.io/en/latest/index.html[BLUE]
        [BLUE]github.com/NonProjects/tgbox[BLUE]

[BRIGHT_BLACK]What should you know about CLI design[BRIGHT_BLACK]
    The CLI (or a Command-Line Interface) is an interface
    that operates with the text input, mostly from the
    user. Unlike the GUI (which is Graphical Interface),
    all interaction with the program are hidden behind the
    raw commands. That's it! You don't even need to use
    your mouse! Using a CMD may seem kinda hard for a green
    users, so if you one of those, -- take a time to read
    about CLI and Terminals right from the Wikipedia:
        [BLUE]en.wikipedia.org/wiki/Command-line_interface[BLUE]

[BRIGHT_BLACK]Working with TGBOX-CLI[BRIGHT_BLACK]
    Builded TGBOX-CLI (as .EXE or just with Python) internally
    doesn't change while working with -- all data is stored
    inside the produced by the API files (LocalBox), so you
    may remove the *executable* at any time, this will not
    affect your saved to Local and pushed to Remote files.

    TGBOX-CLI is a portable: you may drop the .EXE file
    to your USB flash drive and run on any supported OS.

    The Local database (LocalBox) store encrypted by your
    key data. Feel free to save it in a place that can't
    be trusted. [RED]Make sure to use a good encryption key[RED].


[WHITE]ENVIRONMENT VARIABLES[WHITE]
    As many CLI applications, TGBOX-CLI supports some environment
    variables. You can set them in your CMD with the "[MAGENTA]set[MAGENTA]" (Windows)
    or "[MAGENTA]export[MAGENTA]" (UNIX) commands. See more on Wikipedia:
        [BLUE]en.wikipedia.org/wiki/Environment_variable#Syntax[BLUE]

    TGBOX-CLI supports the next environment variables:
        [BRIGHT_WHITE]http_proxy[BRIGHT_WHITE] (or [BRIGHT_WHITE]https_proxy[BRIGHT_WHITE]): setup Proxy (Google for format)
        [BRIGHT_WHITE]TGBOX_CLI_DEBUG[BRIGHT_WHITE]: any value will enable full error Traceback
        [BRIGHT_WHITE]TGBOX_CLI_NOCOLOR[BRIGHT_WHITE]: any value will disable colored output
        [BRIGHT_WHITE]TGBOX_CLI_LOGFILE[BRIGHT_WHITE]: a full path to logging file
        [BRIGHT_WHITE]TGBOX_CLI_LOGLEVEL[BRIGHT_WHITE]: setup logging level (DEBUG/INFO/...etc)
        [BRIGHT_WHITE]TGBOX_CLI_SK[BRIGHT_WHITE]: SessionKey, will be installed on initialization

    [BRIGHT_BLACK]! Ordinary users will may only need the first var to setup Proxy.[BRIGHT_BLACK]

[WHITE]COMMANDS & USAGE[WHITE]
    [BRIGHT_BLACK]! Write a [BRIGHT_BLACK][WHITE]tgbox-cli.exe[WHITE] [BRIGHT_BLACK]if you have .EXE file[BRIGHT_BLACK]

    Try to run a TGBOX-CLI without arguments:
        [BRIGHT_WHITE]tgbox-cli[BRIGHT_WHITE]

    As a result you should see a list of commands. If
    you see an error with text something like "Sorry,
    we don't know such program/file" then locate to
    a folder with executable, open CMD in it and run
    & try once again.

    You can use a [GREEN]--help[GREEN] option with every command
    to get a detailed information about them. Let's
    take a look at first command: the [BLUE]cli-init[BLUE],
    which activates environment for a TGBOX-CLI app:
        [BRIGHT_WHITE]tgbox-cli cli-init --help[BRIGHT_WHITE]

    [BRIGHT_BLACK]! Use a --help every time when you don't understand or[BRIGHT_BLACK]
    [BRIGHT_BLACK]  forgot some command. Fall to this README for examples.[BRIGHT_BLACK]

    Some [BLUE]commands[BLUE] will require you to specify [GREEN]options[GREEN],
    some will prompt you if you don't specify them.

    [WHITE]QUICK INTRO[WHITE]
        [MAGENTA]|||||| Pure Start ||||||[MAGENTA]

        Start with a [BLUE]cli-init[BLUE]:
            [BRIGHT_WHITE]tgbox-cli cli-init[BRIGHT_WHITE]

        This will give you commands for session initialization.
        Write to your terminal proposed ones. Session will
        store your encryption keys so you don't need to
        enter it every time. Your session will be destroyed
        when you will close your command line.

        [RED]We encrypt your Box keys and some other sensitive[RED]
        [RED]information used within session with a TGBOX_SK key. It[RED]
        [RED]is stored in the environment variables, so ANY program[RED]
        [RED]you will run in initialized CMD may recieve a FULL[RED]
        [RED]access to all your keys. To prevent this, always use[RED]
        [RED]a *new* command line instance and DON'T use anything[RED]
        [RED]except the TGBOX-CLI and system tools in initialized CMD.[RED]

        [BRIGHT_BLACK]This is unlikely to happen, but such attack can be done.[BRIGHT_BLACK]

        [RED]Make sure you TRUST the TGBOX-CLI build before going further[RED]

        [MAGENTA]|||||| Connecting Account ||||||[MAGENTA]

        Didn't create any Box? Connect your Telegram account:
            [BRIGHT_WHITE]tgbox-cli account-connect[BRIGHT_WHITE]

        This command will prompt you for phone number linked to
        your Telegram account, login code and password.

        You can connect as many accounts as you want,
        as well as switch between them with the simple
        [BLUE]account-switch[BLUE] command.

        [YELLOW]You can disable TGBOX-CLI session at any time via[YELLOW]
        [YELLOW]Telegram Settings -> Devices if you will need it.[YELLOW]

        [MAGENTA]|||||| Making Box ||||||[MAGENTA]

        You already connected account? Well, it's time to make your
        first Box with the new [BLUE]box-make[BLUE] command! Try this:
            [BRIGHT_WHITE]tgbox-cli box-make[BRIGHT_WHITE]

        [BLUE]box-make[BLUE] command without any [GREEN]options[GREEN] will prompt you
        firstly for name of your new Box. Let's try to specify
        it with [GREEN]option[GREEN], so you can understand how it works:
            [BRIGHT_WHITE]tgbox-cli box-make --box-name=MyBox[BRIGHT_WHITE]

        This will omit "Box name" prompt. Many [GREEN]options[GREEN] can be
        [WHITE]long[WHITE] (with a [WHITE]two[WHITE] dashes [GREEN]--[GREEN]) and [WHITE]short[WHITE] ([WHITE]one[WHITE] dash [GREEN]-[GREEN]) at
        the same time. With a [GREEN]--help[GREEN] on [GREEN]box-make[GREEN] we can see that
        we can write a [GREEN]--box-name[GREEN] as [GREEN]-b[GREEN]:
            [BRIGHT_WHITE]tgbox-cli box-make -b=MyBox[BRIGHT_WHITE]

        [BRIGHT_BLACK]In this README we will write all options in a long variant,[BRIGHT_BLACK]
        [BRIGHT_BLACK]i believe that this will be more easy to learn. Keep in mind[BRIGHT_BLACK]
        [BRIGHT_BLACK]that you can express them in a short way too![BRIGHT_BLACK]

        In the next step the TGBOX-CLI will offer you a randomly
        generated passphrase. You can accept it or specify your
        own. If your choice is a second option, then [RED]make sure
        to specify a strong encryption password[RED], because your
        LocalBox will store a [RED]Telegram session[RED] and file info. The
        key generation process wil require you to give a [RED]1GB of RAM[RED]
        for a couple of seconds. You can adjust amount or make it
        even bigger with the [BLUE]box-make[BLUE] command [GREEN]options[GREEN]. Setting
        [YELLOW]lower amounts of MB per generation will make bruteforcing[YELLOW]
        [YELLOW]a more easy deal[YELLOW], change it only if you're understand
        this. [YELLOW]Make sure to have a free RAM[YELLOW] if you're have an old
        machine, because this may freeze it down until reboot.

        As a result of [BLUE]box-make[BLUE] command you should receive a
        LocalBox file on your computer and private channel (
        the RemoteBox) on your Telegram account. You don't
        need to directly work with RemoteBox at all. All you
        need is just connect your LocalBox and execute the
        [BLUE]commands[BLUE]. As well as with accounts, you can list,
        connect more than one and switch your Boxes. See a
        [BRIGHT_WHITE]tgbox-cli --help[BRIGHT_WHITE] for a list of available [BLUE]commands[BLUE].

        Later you will need to use a [BLUE]box-open[BLUE] to open
        your LocalBox and access files. This one is easy,
        try to close your shell, open it again and connect
        your LocalBox, then go further.

        [MAGENTA]|||||| Uploading Files ||||||[MAGENTA]

        It's time to upload our first file. Let's see how:
            [BRIGHT_WHITE]tgbox-cli file-upload --path path/to/your/file[BRIGHT_WHITE]

        Option [GREEN]--path[GREEN] (or [GREEN]-p[GREEN]) will allow you to specify a path to
        a file that will be prepared, encrypted and pushed to
        your RemoteBox channel. This will work not only for a
        file, but for [WHITE]folders too[WHITE]! You can specify a path to a
        folder and TGBOX-CLI will upload all dirs/files from it.

        [YELLOW]Please note that uploading one big file is always better[YELLOW]
        [YELLOW]than a thousands of small[YELLOW] because we're working around the
        Telegram messenger, and [WHITE]not[WHITE] over the real file server. You
        may end up with a Box that will be really hard to work on
        if your channel will contain i.e 100,000 files or even more.
        |
        [YELLOW]If you have a really big amount of small files[YELLOW], --
        [YELLOW]consider to ZIP them firstly[YELLOW], then upload.

        We can also attach a special attributes -- CAttrs (or
        the "CustomAttributes") to a file before uploading:
            [BRIGHT_WHITE]tgbox-cli file-upload --path Scripts/ --cattrs="tag:code"[BRIGHT_WHITE]

        This will add CAttr with key "tag" and value "code"
        to every file from the folder Scripts/ on upload,
        so you can later search for them with a [BLUE]command[BLUE].

        Those who want to control file uploading at expert
        level should know about [WHITE]balancing[WHITE]. In a theory, we
        can upload simultaneously as much files as we want,
        but in reality the Telegram servers [WHITE]will not like[WHITE]
        thousands of requests per second, which means only
        one -- the flood wait error. To omit this, we limit
        the total size of files uploaded at the same time
        by the [GREEN]--max-bytes[GREEN] option, and the total amount by
        the [GREEN]--max-workers[GREEN]. Algorithm is simple: we will
        iterate over files (if directory specified) and
        adjust the [GREEN]--max-bytes[GREEN] by file size, then
        decrement by one the [GREEN]--max-workers[GREEN]. Upload list
        will expand until [GREEN]--max-workers[GREEN] or [GREEN]--max-bytes[GREEN]
        values > 0, otherwise launch [BLUE]file-upload[BLUE] process.
            By default, [GREEN]--max-bytes[GREEN]=[WHITE]1GB[WHITE] and the
        [GREEN]--max-workers[GREEN]=[WHITE]10[WHITE]; as [BLUE]file-upload[BLUE] should push
        to remote at least one file, -- it [WHITE]will accept[WHITE]
        target which bytesize is > than [GREEN]--max-bytes[GREEN].

        [MAGENTA]|||||| Searching Files ||||||[MAGENTA]

        After you uploaded some files you may list them, try:
            [BRIGHT_WHITE]tgbox-cli file-search[BRIGHT_WHITE]

        [BLUE]file-search[BLUE] without any [CYAN]filters[CYAN] will return you an
        interactive list of all files that was uploaded to
        your Box, however, using [CYAN]them[CYAN] will allow you to
        [WHITE]search[WHITE] for specified files only. See this:
            [BRIGHT_WHITE]tgbox-cli file-search mime=audio max_size=10000000[BRIGHT_WHITE]

        Such [CYAN]filters[CYAN] will search [WHITE]only[WHITE] for audio files (by [CYAN]mime[CYAN]
        type) which size is < than 10MB ([CYAN]max_size[CYAN]). The [CYAN]filters[CYAN]
        [WHITE]isn't[WHITE] [GREEN]options[GREEN] and [WHITE]shouldn't[WHITE] start with dashes. [WHITE]By default[WHITE]
        search works in the "[WHITE]include state[WHITE]": file [WHITE]must match the[WHITE]
        [WHITE]specified filters[WHITE] to be returned, however, there is also
        an "[WHITE]exclude state[WHITE]": [WHITE]matched files isn't returned[WHITE]. You can
        switch this "states" with a [CYAN]special flag[CYAN] that starts with
        the two plus symbols -- [CYAN]++include[CYAN] ([CYAN]+i[CYAN]) and [CYAN]++exclude[CYAN] ([CYAN]+e[CYAN])
        |
        A file should be matched by [WHITE]all[WHITE] [CYAN]filters[CYAN] to be returned
        (works like [RED]AND[RED]), after one mismatch file will be skipped.
        |
        This will return all audio files except the FLAC:
            [BRIGHT_WHITE]tgbox-cli file-search mime=audio ++exclude mime=x-flac[BRIGHT_WHITE]

        [YELLOW]See[YELLOW] [BRIGHT_WHITE]tgbox-cli file-search --help[BRIGHT_WHITE] [YELLOW]for all supported filters.[YELLOW]

        [MAGENTA]|||||| Downloading Files ||||||[MAGENTA]

        File downloading is often a simple routine. See this:
            [WHITE]tgbox-cli file-download max_id=100 +e mime=video[WHITE]

        The [BLUE]file-download[BLUE] will search a target files by [CYAN]filters[CYAN]
        (like [BLUE]file-search[BLUE]) and download them to the [WHITE]DownloadsTGBOX[WHITE]
        folder, [WHITE]preserving[WHITE] the actual file path. The command above
        will download all files that [WHITE]ID is < 100[WHITE] & [WHITE]mime type of[WHITE]
        [WHITE]which is not a video[WHITE]. This is only an example, [BLUE]file-download[BLUE]
        support all of the [CYAN]filters[CYAN] that support [BLUE]file-search[BLUE].

        You can specify [GREEN]--locate[GREEN] flag to open downloaded file
        in a file explorer (system default), as well as the
        [GREEN]--show[GREEN] to open it (by the system default app by the
        mime type). The last can be useful i.e to watch big
        video while it's being downloaded. [YELLOW]Make sure to use[YELLOW]
        [YELLOW]it on a single download[YELLOW], otherwise it can be a [WHITE]mess[WHITE].

        [BLUE]file-download[BLUE] support [WHITE]balancing[WHITE] via [GREEN]--max-bytes[GREEN] and
        the [GREEN]--max-workers[GREEN] options. See the end of the
        [MAGENTA]Uploading Files[MAGENTA] chapter to master this.

        [MAGENTA]|||||| Removing Files ||||||[MAGENTA]

        You can easily remove uploaded files by [CYAN]filters[CYAN]:
            [WHITE]tgbox-cli file-remove mime=image +e file_name=2023[WHITE]

        The command in this example will [WHITE]delete[WHITE] all images
        from your [WHITE]Local and Remote[WHITE] boxes except those who
        have a "2023" in a file name. Sure, [BLUE]file-remove[BLUE]
        support all of the [CYAN]filters[CYAN] described before. You
        can also remove files [WHITE]from the LocalBox only[WHITE] by
        using the [GREEN]--local[GREEN] flag and force TGBOX-CLI to
        [WHITE]ask you[WHITE] for each file by the [GREEN]--ask-before-remove[GREEN].

        [MAGENTA]|||||| Changing File attributes ||||||[MAGENTA]

        The default file attributes (not CAttrs) is the
        [WHITE]mime[WHITE], [WHITE]file_name[WHITE], [WHITE]file_path[WHITE], ... etc. Probably the
        most interesting is the last two, as you may want
        to [WHITE]change name or path[WHITE] of some file(s). This can
        be easily done via [BLUE]file-attr-change[BLUE] command:
            [WHITE]tgbox-cli file-attr-change mime=image -a\[WHITE]
                [WHITE]file_path=/home/non/Pictures[WHITE]

        As you can see, selecting is done by [CYAN]filters[CYAN]. We
        specify attribute with the [GREEN]--attribute[GREEN] ([GREEN]-a[GREEN])
        option. The example above will [WHITE]change[WHITE] the
        file path of every image in your Box [WHITE]to[WHITE]
        [WHITE]/home/non/Pictures[WHITE] path. We can say that
        this is something like "[WHITE]move to[WHITE]" operation.

        [BRIGHT_BLACK]! The same can be done with the "file_name"[BRIGHT_BLACK]

        [YELLOW]Please note[YELLOW] that we [WHITE]can not[WHITE] change file after it
        was uploaded, so we store your updates encrypted
        in the Telegram File "[WHITE]caption[WHITE]". It has limit of
        [WHITE]~2KB[WHITE] and [WHITE]~4KB[WHITE] for Telegram [WHITE]Premium[WHITE] users.

    [WHITE]EXTENDED USAGE[WHITE]
        [MAGENTA]|||||| Box Sharing ||||||[MAGENTA]

        Let's assume that we have two friends: the [RED]A[RED]lice
        and [CYAN]B[CYAN]ob. [RED]Alice[RED] want to share her Box with [CYAN]Bob[CYAN].

        [WHITE]Step one[WHITE]: [RED]Alice[RED] [WHITE]should add[WHITE] [CYAN]Bob[CYAN] to her RemoteBox
        [WHITE]Telegram channel[WHITE] and [YELLOW]optionally[YELLOW] grant some admin
        permissions, so [CYAN]Bob[CYAN] [WHITE]will be able to upload files[WHITE]
        by himself and not download-only. This will be
        done [WHITE]outside of TGBOX-CLI[WHITE], by the [WHITE]Telegram app[WHITE];
        [BRIGHT_BLACK]|[BRIGHT_BLACK]
        [WHITE]Step two[WHITE] [BRIGHT_BLACK](after Alice added Bob to her RemoteBox)[BRIGHT_BLACK]:
        [CYAN]Bob[CYAN] will need to use a [BLUE]box-list-remote[BLUE] command to
        list & find [RED]Alice[RED]'s shiny Box. This command will
        return numbered [WHITE]list of all RemoteBoxes[WHITE] found on
        account. [CYAN]Bob[CYAN] [WHITE]will need to take a number[WHITE] of the
        corresponding [RED]Alice[RED]'s [WHITE]RemoteBox[WHITE] to go further;
        [BRIGHT_BLACK]|[BRIGHT_BLACK]
        [WHITE]Step three[WHITE]: [CYAN]Bob[CYAN] will need to [WHITE]make a RequestKey[WHITE]
        to [RED]Alice[RED]'s RemoteBox. This can be easily done via
        [BLUE]box-request[BLUE] command. Previously obtained number
        should be specified [WHITE]as the[WHITE] [GREEN]--number[GREEN]. [CYAN]Bob[CYAN] [WHITE]will[WHITE]
        [WHITE]share received RequestKey with the[WHITE] [RED]Alice[RED];
        [BRIGHT_BLACK]|[BRIGHT_BLACK]
        [WHITE]Step four[WHITE]: [RED]A[RED] will make [WHITE]a ShareKey[WHITE] with the [CYAN]B[CYAN]'s
        [WHITE]RequestKey and the[WHITE] [BLUE]box-share[BLUE] command. Key of [CYAN]B[CYAN]
        must be specified as [GREEN]--requestkey[GREEN] option. [RED]A[RED]
        [WHITE]will share[WHITE] resulted ShareKey with the [CYAN]B[CYAN];
        [BRIGHT_BLACK]|[BRIGHT_BLACK]
        [WHITE]Step five[WHITE]: [CYAN]B[CYAN] [WHITE]will use ShareKey and[WHITE] [BLUE]box-clone[BLUE]
        command [WHITE]to clone RemoteBox[WHITE] and make a LocalBox;
        ShareKey must be specified as [GREEN]--key[GREEN] and the
        number of RemoteBox as [GREEN]--number[GREEN].
        [BRIGHT_BLACK]*[BRIGHT_BLACK]
        [GREEN]Done![GREEN]

        Real Box encryption key (the [WHITE]MainKey[WHITE]) is safely
        encrypted with the end-to-end [WHITE]ECDH[WHITE] algorithm, so
        [RED]Alice[RED] and [CYAN]Bob[CYAN] [YELLOW]can exchange[YELLOW] [WHITE]ShareKey[WHITE] and [WHITE]RequestKey[WHITE]
        [YELLOW]via insecure canals[YELLOW] & [WHITE]only[WHITE] [CYAN]B[CYAN] will be able to use
        ShareKey received from [RED]A[RED] to clone RemoteBox.

        [MAGENTA]|||||| Box Syncing ||||||[MAGENTA]

        Box needs to be synced [WHITE]if[WHITE] it's used by multiply
        peoples & [WHITE]if[WHITE] at least one upload files. This can be
        done with the [BLUE]box-sync[BLUE] command. [WHITE]By default[WHITE], TGBOX-CLI
        will try to use a [CYAN]Fast Sync[CYAN]: the synchronization
        [WHITE]from the[WHITE] Telegram Channel [WHITE]Admin Log[WHITE]; obviously
        this will require You [WHITE]to have admin rights[WHITE]; or,
        to be more specific, You must to be [WHITE]at least[WHITE]
        [WHITE]Admin with zero rights[WHITE] (all rights off). Ask
        the Box owner to make you such Admin. Note
        that you need to sync [WHITE]within 48 hours[WHITE] after
        file was uploaded, cuz later Log will be cleared.

        Alternatively, you can make a [CYAN]Deep Sync[CYAN]. It
        can be enabled by specifying the [GREEN]--deep[GREEN] flag.

        The [BLUE]box-sync[BLUE] [GREEN]--deep[GREEN] without additional options
        will check [WHITE]every file[WHITE] in RemoteBox and compare it
        with one from LocalBox. Typically we [WHITE]don't[WHITE]
        need a full synchronization, because it can be
        [WHITE]really[WHITE] slow and useless. We can track a state of
        our LocalBox and RemoteBox with the [BLUE]box-info[BLUE]
        command. If your remote is ahead, use a
        [GREEN]--start-from-id[GREEN] on [BLUE]box-sync[BLUE] and specify it as
        last file ID in your LocalBox. This will
        download all info about latest pushed files.

        [MAGENTA]|||||| File Sharing ||||||[MAGENTA]

        W.I.P: <TODO>
