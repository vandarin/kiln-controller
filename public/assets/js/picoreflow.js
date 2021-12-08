var state = "IDLE";
var state_last = "";
var graphs = {};
var points = [];
var profiles = [];
var time_mode = 0;
var selected_profile = 0;
var selected_profile_name = '_monitor-only.json';
var temp_scale = "c";
var time_scale_slope = "s";
var time_scale_profile = "s";
var time_scale_long = "Seconds";
var temp_scale_display = "C";
var kwh_rate = 0.26;
var hazard_temp = 1200;
var currency_type = "EUR";
var timeout_ids = [];
var debug_console = false;
var graph_colors = [
    'rgba(194, 119, 182, 0.8)',
    'rgba(245, 100, 89, 0.8)',
    'rgba(250, 185, 80, 0.8)',
    'rgba(200, 110, 0, 0.8)',
    'rgba(220, 95, 82, 0.8)',
];
var protocol = 'ws:';
if (window.location.protocol == 'https:') {
    protocol = 'wss:';
}
var host = "" + protocol + "//" + window.location.hostname + ":" + window.location.port;


// wait for config before opening other sockets
var ws_config, ws_status, ws_control, ws_storage;

graphs.profile =
{
    label: "Profile",
    data: [],
    points: { show: false },
    color: "rgba(20,250,50,0.8)",
    draggable: false
};

graphs.live =
{
    label: "AVG",
    data: [],
    points: { show: false },
    color: "rgba(250, 200, 270, 0.5)",
    lines: { lineWidth: 7 },
    draggable: false
};

function _c_to_temp_scale(value) {
    if (temp_scale == 'f') {
        return (value * 9 / 5) + 32;
    }
    return value;
}

function updateProfile(id) {
    selected_profile = id;
    selected_profile_name = profiles[id].name;
    var job_seconds = profiles[id].data.length === 0 ? 0 : parseInt(profiles[id].data[profiles[id].data.length - 1][0]);
    var kwh = (3850 * job_seconds / 3600 / 1000).toFixed(2);
    var cost = (kwh * kwh_rate).toFixed(2);
    var job_time = new Date(job_seconds * 1000).toISOString().substr(11, 8);
    $('#sel_prof').html(profiles[id].name);
    $('#sel_prof_eta').html(job_time);
    $('#sel_prof_cost').html(kwh + ' kWh (' + currency_type + ': ' + cost + ')');
    graphs.profile.data = profiles[id].data;
    updateGraph();
}

function deleteProfile() {
    var profile = { "type": "profile", "data": "", "name": selected_profile_name };
    var delete_struct = { "cmd": "DELETE", "profile": profile };

    var delete_cmd = JSON.stringify(delete_struct);
    console.log("Delete profile:" + selected_profile_name);

    ws_storage.send(delete_cmd);

    ws_storage.send('GET');
    selected_profile_name = profiles[0].name;

    state = "IDLE";
    $('#edit').hide();
    $('#profile_selector').show();
    $('#btn_controls').show();
    $('#status').slideDown();
    $('#profile_table').slideUp();
    $('#e2').select2('val', 0);
    graphs.profile.points.show = false;
    graphs.profile.draggable = false;
    plot = $.plot("#graph_container", Object.values(graphs), getOptions());
}


function updateProgress(percentage) {
    if (state == "RUNNING") {
        if (percentage > 100) percentage = 100;
        $('#progressBar').css('width', percentage + '%');
        if (percentage > 5) $('#progressBar').html(parseInt(percentage) + '%');
    }
    else {
        $('#progressBar').css('width', 0 + '%');
        $('#progressBar').html('');
    }
}

function updateProfileTable() {
    var dps = 0;
    var slope = "";
    var color = "";

    var html = '<h3>Schedule Points</h3><div class="table-responsive" style="scroll: none"><table class="table table-striped">';
    html += '<tr><th style="width: 50px">#</th><th>Target Time in ' + time_scale_long + '</th><th>Target Temperature in °' + temp_scale_display + '</th><th>Slope in &deg;' + temp_scale_display + '/' + time_scale_slope + '</th><th></th></tr>';

    for (var i = 0; i < graphs.profile.data.length; i++) {

        if (i >= 1) dps = ((graphs.profile.data[i][1] - graphs.profile.data[i - 1][1]) / (graphs.profile.data[i][0] - graphs.profile.data[i - 1][0]) * 10) / 10;
        if (dps > 0) { slope = "up"; color = "rgba(206, 5, 5, 1)"; } else
            if (dps < 0) { slope = "down"; color = "rgba(23, 108, 204, 1)"; dps *= -1; } else
                if (dps == 0) { slope = "right"; color = "grey"; }

        html += '<tr><td><h4>' + (i + 1) + '</h4></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-0-' + i + '" value="' + timeProfileFormatter(graphs.profile.data[i][0], true) + '" style="width: 60px" /></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-1-' + i + '" value="' + graphs.profile.data[i][1] + '" style="width: 60px" /></td>';
        html += '<td><div class="input-group"><span class="glyphicon glyphicon-circle-arrow-' + slope + ' input-group-addon ds-trend" style="background: ' + color + '"></span><input type="text" class="form-control ds-input" readonly value="' + formatDPS(dps) + '" style="width: 100px" /></div></td>';
        html += '<td>&nbsp;</td></tr>';
    }

    html += '</table></div>';

    $('#profile_table').html(html);

    //Link table to graph
    $(".form-control").change(function (e) {
        var id = $(this)[0].id; //e.currentTarget.attributes.id
        var value = parseInt($(this)[0].value);
        var fields = id.split("-");
        var col = parseInt(fields[1]);
        var row = parseInt(fields[2]);

        if (graphs.profile.data.length > 0) {
            if (col == 0) {
                graphs.profile.data[row][col] = timeProfileFormatter(value, false);
            }
            else {
                graphs.profile.data[row][col] = value;
            }

            plot = $.plot("#graph_container", Object.values(graphs), getOptions());
        }
        updateProfileTable();

    });
}

function timeProfileFormatter(val, down) {
    var rval = val
    switch (time_scale_profile) {
        case "m":
            if (down) { rval = val / 60; } else { rval = val * 60; }
            break;
        case "h":
            if (down) { rval = val / 3600; } else { rval = val * 3600; }
            break;
    }
    return Math.round(rval);
}

function formatDPS(val) {
    var tval = val;
    if (time_scale_slope == "m") {
        tval = val * 60;
    }
    if (time_scale_slope == "h") {
        tval = (val * 60) * 60;
    }
    return Math.round(tval);
}

function hazardTemp() {
    return hazard_temp;
}

function timeTickFormatter(val) {
    if (val < 1800) {
        return val;
    }
    else {
        var hours = Math.floor(val / (3600));
        var div_min = val % (3600);
        var minutes = Math.floor(div_min / 60);

        if (hours < 10) { hours = "0" + hours; }
        if (minutes < 10) { minutes = "0" + minutes; }

        return hours + ":" + minutes;
    }
}

function runTask() {
    var cmd =
    {
        "cmd": "RUN",
        "profile": profiles[selected_profile]
    }

    for (const series in graphs) {
        if (series == "profile") {
            continue;
        }
        graphs[series].data = [];
    }
    graphs.live.data = [];
    updateGraph();

    ws_control.send(JSON.stringify(cmd));

}

function runTaskSimulation() {
    var cmd =
    {
        "cmd": "SIMULATE",
        "profile": profiles[selected_profile]
    }

    graphs.live.data = [];
    updateGraph();

    ws_control.send(JSON.stringify(cmd));

}


function abortTask() {
    var cmd = { "cmd": "STOP" };
    ws_control.send(JSON.stringify(cmd));
}

function enterNewMode() {
    state = "EDIT"
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    $('#form_profile_name').attr('value', '');
    $('#form_profile_name').attr('placeholder', 'Please enter a name');
    graphs.profile.points.show = true;
    graphs.profile.draggable = true;
    graphs.profile.data = [];
    plot = $.plot("#graph_container", Object.values(graphs), getOptions());
    updateProfileTable();
}

function enterEditMode() {
    state = "EDIT"
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    console.log(profiles);
    $('#form_profile_name').val(profiles[selected_profile].name);
    graphs.profile.points.show = true;
    graphs.profile.draggable = true;
    plot = $.plot("#graph_container", Object.values(graphs), getOptions());
    updateProfileTable();
}

function leaveEditMode() {
    selected_profile_name = $('#form_profile_name').val();
    ws_storage.send('GET');
    state = "IDLE";
    $('#edit').hide();
    $('#profile_selector').show();
    $('#btn_controls').show();
    $('#status').slideDown();
    $('#profile_table').slideUp();
    graphs.profile.points.show = false;
    graphs.profile.draggable = false;
    plot = $.plot("#graph_container", Object.values(graphs), getOptions());
}

function newPoint() {
    if (graphs.profile.data.length > 0) {
        var pointx = parseInt(graphs.profile.data[graphs.profile.data.length - 1][0]) + 15;
    }
    else {
        var pointx = 0;
    }
    graphs.profile.data.push([pointx, Math.floor((Math.random() * 230) + 25)]);
    plot = $.plot("#graph_container", Object.values(graphs), getOptions());
    updateProfileTable();
}

function delPoint() {
    graphs.profile.data.splice(-1, 1)
    plot = $.plot("#graph_container", Object.values(graphs), getOptions());
    updateProfileTable();
}

function toggleTable() {
    if ($('#profile_table').css('display') == 'none') {
        $('#profile_table').slideDown();
    }
    else {
        $('#profile_table').slideUp();
    }
}

function saveProfile() {
    var name = $('#form_profile_name').val();
    var rawdata = plot.getData()[0].data
    var data = [];
    var last = -1;

    for (var i = 0; i < rawdata.length; i++) {
        if (rawdata[i][0] > last) {
            data.push([rawdata[i][0], rawdata[i][1]]);
        }
        else {
            $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 88:</b><br/>An oven is not a time-machine", {
                ele: 'body', // which element to append to
                type: 'alert', // (null, 'info', 'error', 'success')
                offset: { from: 'top', amount: 250 }, // 'top', or 'bottom'
                align: 'center', // ('left', 'right', or 'center')
                width: 385, // (integer, or 'auto')
                delay: 5000,
                allow_dismiss: true,
                stackup_spacing: 10 // spacing between consecutively stacked growls.
            });

            return false;
        }

        last = rawdata[i][0];
    }

    var profile = { "type": "profile", "data": data, "name": name }
    var put = { "cmd": "PUT", "profile": profile }

    var put_cmd = JSON.stringify(put);

    ws_storage.send(put_cmd);

    leaveEditMode();
}

function getOptions() {

    var options =
    {
        series:
        {
            lines:
            {
                show: true
            },

            points:
            {
                show: true,
                radius: 5,
                symbol: "circle"
            },

            shadowSize: 3

        },
        xaxis:
        {
            min: 0,
            tickColor: 'rgba(216, 211, 197, 0.2)',
            tickFormatter: timeTickFormatter,
            font:
            {
                size: 14,
                lineHeight: 14, weight: "normal",
                family: "Digi",
                variant: "small-caps",
                color: "rgba(216, 211, 197, 0.85)"
            }
        },

        yaxis:
        {
            min: 0,
            tickDecimals: 0,
            draggable: false,
            tickColor: 'rgba(216, 211, 197, 0.2)',
            font:
            {
                size: 14,
                lineHeight: 14,
                weight: "normal",
                family: "Digi",
                variant: "small-caps",
                color: "rgba(216, 211, 197, 0.85)"
            }
        },

        grid:
        {
            color: 'rgba(216, 211, 197, 0.55)',
            borderWidth: 1,
            labelMargin: 10,
            mouseActiveRadius: 50,
            markings: function (axes) {
                var markings = [
                    { yaxis: { from: 0, to: _c_to_temp_scale(100), }, color: 'rgba(0,100,250,0.2)' },
                    { yaxis: { from: _c_to_temp_scale(600), to: _c_to_temp_scale(700), }, color: 'rgba(120,0,0,0.2)' },
                    { yaxis: { from: _c_to_temp_scale(700), to: _c_to_temp_scale(900), }, color: 'rgba(255,0,0,0.2)' },
                    { yaxis: { from: _c_to_temp_scale(900), to: _c_to_temp_scale(1100), }, color: 'rgba(255,153,0,0.2)' },
                    { yaxis: { from: _c_to_temp_scale(1100), to: _c_to_temp_scale(1300), }, color: 'rgba(255,255,102,0.2)' },
                ];
                for (var x = Math.floor(axes.xaxis.min); x < axes.xaxis.max; x += 120 * 60)
                    markings.push({ xaxis: { from: x, to: x + (60 * 60) }, color: 'rgba(120,120,120,0.2)' });
                return markings;
            }

        },

        legend:
        {
            show: true,
            position: 'se',
        }
    }

    return options;

}
function updateGraph() {
    plot = $.plot("#graph_container", Object.values(graphs), getOptions());
}

function createZoneDisplay(zones) {

    zones.forEach(zone => {
        $("#state_head").before(`<div class="ds-title zone">${zone.Name}</div>`);
        $("#state").before(`<div class="display ds-num"><span id="${zone.Name}_temp"></span><span class="ds-unit act_temp_scale">&deg;C</span>`)
        if (zone.Heated) {
            $("#hazard").before(`<span class="ds-led" id="${zone.Name}_heat">&#9832;</span>`)
            graphs[zone.Name] = {
                label: zone.Name,
                data: [],
                points: { show: false },
                color: graph_colors.pop(),
                draggable: false
            }
        }
    });
}


$(document).ready(function () {


    if (!("WebSocket" in window)) {
        $('#chatLog, input, button, #examples').fadeOut("fast");
        $('<p>Oh no, you need a browser that supports WebSockets. How about <a href="http://www.google.com/chrome">Google Chrome</a>?</p>').appendTo('#container');
    }
    else {
        ws_config = new WebSocket(host + "/config");
        // Config Socket /////////////////////////////////

        ws_config.onopen = function () {
            ws_config.send('GET');
        };

        ws_config.onmessage = function (e) {
            console.log(e.data);
            x = JSON.parse(e.data);
            temp_scale = x.temp_scale;
            time_scale_slope = x.time_scale_slope;
            time_scale_profile = x.time_scale_profile;
            kwh_rate = x.kwh_rate;
            currency_type = x.currency_type;
            hazard_temp = x.hazard_temp;

            createZoneDisplay(x.zones);

            if (temp_scale == "c") { temp_scale_display = "C"; } else { temp_scale_display = "F"; }


            $('.act_temp_scale').html('º' + temp_scale_display);
            $('#target_temp_scale').html('º' + temp_scale_display);

            switch (time_scale_profile) {
                case "s":
                    time_scale_long = "Seconds";
                    break;
                case "m":
                    time_scale_long = "Minutes";
                    break;
                case "h":
                    time_scale_long = "Hours";
                    break;
            }
            openSockets();
        }
        function openSockets() {
            ws_status = new WebSocket(host + "/status");
            ws_control = new WebSocket(host + "/control");
            ws_storage = new WebSocket(host + "/storage");

            // Status Socket ////////////////////////////////

            ws_status.onopen = function () {
                console.log("Status Socket has been opened");

                $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span>Getting data from server",
                    {
                        ele: 'body', // which element to append to
                        type: 'success', // (null, 'info', 'error', 'success')
                        offset: { from: 'top', amount: 250 }, // 'top', or 'bottom'
                        align: 'center', // ('left', 'right', or 'center')
                        width: 385, // (integer, or 'auto')
                        delay: 2500,
                        allow_dismiss: true,
                        stackup_spacing: 10 // spacing between consecutively stacked growls.
                    });
            };

            ws_status.onclose = function () {
                $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 1:</b><br/>Status Websocket not available", {
                    ele: 'body', // which element to append to
                    type: 'error', // (null, 'info', 'error', 'success')
                    offset: { from: 'top', amount: 250 }, // 'top', or 'bottom'
                    align: 'center', // ('left', 'right', or 'center')
                    width: 385, // (integer, or 'auto')
                    delay: 5000,
                    allow_dismiss: true,
                    stackup_spacing: 10 // spacing between consecutively stacked growls.
                });
            };

            ws_status.onmessage = function (e) {
                if (debug_console) {
                    console.log("received status data")
                    console.log(e.data);
                }
                x = JSON.parse(e.data);
                if (x.type == "backlog") {
                    if (x.profile) {
                        selected_profile_name = x.profile.name;
                        $.each(profiles, function (i, v) {
                            if (v.name == x.profile.name) {
                                updateProfile(i);
                                $('#e2').select2('val', i);
                            }
                        });
                    }

                    $.each(x.log, function (i, v) {
                        graphs.live.data.push([v.runtime, v.temperature]);
                        v.zones.forEach(zone => {
                            if (zone.Heated) {
                                graphs[zone.Name].data.push([v.runtime, zone.Temp]);
                            }
                        });
                    });
                    updateGraph();
                }

                if (state != "EDIT") {
                    state = x.state;

                    if (state != state_last) {
                        if (state_last == "RUNNING") {
                            $('#target_temp').html('---');
                            updateProgress(0);
                            $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>Run completed</b>", {
                                ele: 'body', // which element to append to
                                type: 'success', // (null, 'info', 'error', 'success')
                                offset: { from: 'top', amount: 250 }, // 'top', or 'bottom'
                                align: 'center', // ('left', 'right', or 'center')
                                width: 385, // (integer, or 'auto')
                                delay: 0,
                                allow_dismiss: true,
                                stackup_spacing: 10 // spacing between consecutively stacked growls.
                            });
                        }
                    }

                    if (state == "RUNNING") {
                        $("#nav_start").hide();
                        $("#nav_stop").show();

                        graphs.live.data.push([x.runtime, x.temperature]);
                        x.zones.forEach(zone => {
                            if (!zone.Heated) {
                                return;
                            }
                            graphs[zone.Name].data.push([x.runtime, zone.Temp])
                        });
                        updateGraph();

                        left = parseInt(x.totaltime - x.runtime);
                        eta = new Date(left * 1000).toISOString().substr(11, 8);

                        updateProgress(parseFloat(x.runtime) / parseFloat(x.totaltime) * 100);

                        leftDate = new Date();
                        leftDate.setSeconds(leftDate.getSeconds() + left);
                        endtime = leftDate.toTimeString().substr(0, 8);
                        $('#state').html('<span class="glyphicon glyphicon-time" style="font-size: 22px; font-weight: normal"></span><span title="' + endtime + '" style="font-family: Digi; font-size: 30px;">' + eta + '</span>');
                        $('#target_temp').html(parseInt(x.target));


                    }
                    else {
                        $("#nav_start").show();
                        $("#nav_stop").hide();
                        $('#state').html('<p class="ds-text">' + state + '</p>');
                    }

                    $('#act_temp').html(parseInt(x.temperature));
                    if (x.zones) {
                        x.zones.forEach(zone => {
                            $(`#${zone.Name}_temp`).html(parseInt(zone.Temp));
                            if (zone.Heat > 0.0) {
                                // if (timeout_ids[zone.Name]) {
                                //     clearTimeout(timeout_ids[zone.Name]);
                                // }
                                setTimeout(function () { $(`#${zone.Name}_heat`).addClass("ds-led-heat-active"); }, 0)
                                timeout_ids[zone.Name] = setTimeout(function () { $(`#${zone.Name}_heat`).removeClass("ds-led-heat-active") }, (zone.Heat * 1000.0) - 5)
                            }
                        });

                    }

                    if (x.temperature > hazardTemp()) { $('#hazard').addClass("ds-led-hazard-active"); } else { $('#hazard').removeClass("ds-led-hazard-active"); }

                    state_last = state;
                }
            };

            // Control Socket ////////////////////////////////

            ws_control.onopen = function () {

            };

            ws_control.onmessage = function (e) {
                //Data from Simulation
                console.log("control socket has been opened")
                console.log(e.data);
                x = JSON.parse(e.data);
                graphs.live.data.push([x.runtime, x.temperature]);
                updateGraph();

            }

            // Storage Socket ///////////////////////////////

            ws_storage.onopen = function () {
                ws_storage.send('GET');
            };


            ws_storage.onmessage = function (e) {
                message = JSON.parse(e.data);

                if (message.resp) {
                    if (message.resp == "FAIL") {
                        if (confirm('Overwrite?')) {
                            message.force = true;
                            console.log("Sending: " + JSON.stringify(message));
                            ws_storage.send(JSON.stringify(message));
                        }
                        else {
                            //do nothing
                        }
                    }

                    return;
                }

                //the message is an array of profiles
                //FIXME: this should be better, maybe a {"profiles": ...} container?
                profiles = message;
                //delete old options in select
                $('#e2').find('option').remove().end();
                // check if current selected value is a valid profile name
                // if not, update with first available profile name
                var valid_profile_names = profiles.map(function (a) { return a.name; });
                if (
                    valid_profile_names.length > 0 &&
                    $.inArray(selected_profile_name, valid_profile_names) === -1
                ) {
                    selected_profile = 0;
                    selected_profile_name = valid_profile_names[0];
                }

                // fill select with new options from websocket
                for (var i = 0; i < profiles.length; i++) {
                    var profile = profiles[i];
                    //console.log(profile.name);
                    $('#e2').append('<option value="' + i + '">' + profile.name + '</option>');

                    if (profile.name == selected_profile_name) {
                        selected_profile = i;
                        $('#e2').select2('val', i);
                        updateProfile(i);
                    }
                }
            };
        }

        $("#e2").select2(
            {
                placeholder: "Select Profile",
                allowClear: true,
                minimumResultsForSearch: -1
            });


        $("#e2").on("change", function (e) {
            updateProfile(e.val);
        });

    }
});
