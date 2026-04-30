function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === (name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

$(document).ready(function() {
    $('#custom_navbar_logo_img').on('click',function(){
        window.location = "/"
    });
    $('#branch_name_dropdown').select2({ placeholder: "" });
    $('#train_name_dropdown').select2({ placeholder: "" });
    $('#build_name_dropdown').select2({ placeholder: "" });
    $('#category_dropdown').select2({ placeholder: "" });
    $('#squad_dropdown').select2({ placeholder: "" });
    $('#suite_tag').select2({ placeholder: "" });

    $('#branch_name_dropdown').on('change', function() {
        var branch = $(this).val();
        $('#train_name_dropdown').empty();
        $('#build_name_dropdown').empty();
        $('#build_name_dropdown').append('<option></option>');
        $.ajax({
            url: "/trainname_by_branch/"+branch,
            type: "GET",
            dataType: "json",
            success: function(data) {
                $('#train_name_dropdown').empty();
                $('#train_name_dropdown').append('<option></option>');
                $.each(data, function(key,value){
                    $('#train_name_dropdown').append('<option value="'+value+'">'+value+'</option>');
                });
            }
        });
    });
    $('#train_name_dropdown').on('change', function() {
        var trainname = $(this).val();
        var branch = $('#branch_name_dropdown').val()
        if (trainname.includes('ui')){
            $(".severe_log_text").removeClass('hidden').addClass("show");
        } else {
            $(".severe_log_text").removeClass('show').addClass("hidden");
        }
        $.ajax({
            url: "/build_by_branch_train/"+branch+"/"+trainname,
            type: "GET",
            dataType: "json",
            success: function(data) {
                $('#build_name_dropdown').empty();
                $('#build_name_dropdown').append('<option></option>');
                $.each(data.builds, function(key,value){
                    $('#build_name_dropdown').append('<option>'+value+'</option>');
                });
                $('#squad_dropdown').empty();
                $('#squad_dropdown').append('<option value="all">All</option>');
                $.each(data.squad, function(key,value){
                    $('#squad_dropdown').append('<option>'+value+'</option>');
                });
                if (data.tags) {
                    $('#suite_tag').empty();
                    $('#suite_tag').append('<option value="all">All</option>');
                    $.each(data.tags, function(key,value){
                        $('#suite_tag').append('<option>'+value+'</option>');
                    });
                    $('.suite_tag_parent').removeClass('display_none');
                    $('#suite_tag').select2({ placeholder: "" });
                } else {
                    if(!$('.suite_tag_parent').hasClass('display_none')){
                        $('.suite_tag_parent').addClass('display_none');
                    }
                    $('#suite_tag').empty();
                    $('#suite_tag').append('<option value="all">All</option>');
                    $('#suite_tag').select2({ placeholder: "" });
                }
            }
        });
    });

    $('#category_dropdown').on('change', function() {
        var category =  $(this).val();
        var trainname = $('#train_name_dropdown').val();
        if (category == "error" && trainname.includes('ui')){
            $(".severe_log_text").removeClass('hidden').addClass("show");
        } else {
            $(".severe_log_text").removeClass('show').addClass("hidden");
        }
    });

    $('#SearchSolButton').on('click',function(){
        var error_input = $('#searchsolutions').val();
        if (error_input == "") {
            errorMsg = "Please specify the error message for search"
            $(".search_solution_result").empty();
            $('.search_solution_result').css("visibility","hidden");
            $("#homesnackbarError #homesnackbarErrorMsg").empty().append(errorMsg);
            $("#homesnackbarError").addClass("show");
            setTimeout(function() { $("#homesnackbarError").removeClass("show"); }, 10000);
        } else {
             $.ajax({
                url: "/submit_search_engine_error/",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    error_input: error_input}),
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                success: function(data) {
                    $(".search_solution_result").empty();
                    $('.search_solution_result').css("height","50vh");
                    $(".search_solution_result").append(data.solution);
                    $(".search_solution_result").addClass("show");
                },
                error:function (xhr, ajaxOptions, thrownError){
                    if (xhr.status==500) {
                        errorMsg = "Error:" + $($.parseHTML(xhr.responseText)).filter("title").text();
                        errorMsg += ". Please contact dev team."
                        $("#homesnackbarError#homesnackbarErrorMsg").empty().append(errorMsg);
                        $("#homesnackbarError#homesnackbarErrorMsg").addClass("show");
                        setTimeout(function() { $("#homesnackbarError#homesnackbarErrorMsg").removeClass("show"); }, 10000);
                    }
                }
            });
        }
    });

    $("#start_analyze_train").on("click", function(){
        var branch = $('#branch_name_dropdown').val();
        var trainname = $("#train_name_dropdown").val();
        var build = $('#build_name_dropdown').val();
        var analyze_category = $('#category_dropdown').val();
        var squad = $('#squad_dropdown').val();
        var severe_log = $("#withseverelog").is(':checked')
        var suite_tag = $('#suite_tag').val();
        if(branch=="" || trainname=="" || build=="" ||  analyze_category==""){
            $("#analyze_train_error_message").removeClass("hidden");
            $("#analyze_train_error_message").addClass("show");
            setTimeout(function() { $("#analyze_train_error_message").removeClass("show"); }, 10000);
        }
        if(squad==""){
            squad = "all"
        }
        $('#train_analyzed_result').empty();
        if(branch!="" && trainname!="" && build!="" && analyze_category!=""){
            $('#home_page_body_content').hide();
            $('#home_page_welcome_msg').hide();
            $("#train_analyzed_result").append('<div class="loader"></div>');
            $.ajax({
                url: "/analyze_result_v2/",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    branch: branch,
                    trainname:trainname,
                    build:build,
                    category:analyze_category,
                    squad:squad,
                    severe: severe_log,
                    tag: suite_tag
                }),
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                success: function(data) {
                    if (data.errordata) {
                        if ((data.errordata).length == 0){
                            $('#home_page_body_content').show();
                            $('#home_page_welcome_msg').show();
                            $('#train_analyzed_result').empty();
                            errorMsg = "Info: No errors found!";
                            $("#homesnackbarSuccess #homesnackbarSuccessMsg").empty().append(errorMsg);
                            $("#homesnackbarSuccess").addClass("show");
                            setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 60000);
                            return;
                        }
                    } else if (data.suitedata) {
                        if ((data.suitedata) == 0) {
                            $('#home_page_body_content').show();
                            $('#home_page_welcome_msg').show();
                            $('#train_analyzed_result').empty();
                            errorMsg = "Info: No errors found!";
                            $("#homesnackbarSuccess #homesnackbarSuccessMsg").empty().append(errorMsg);
                            $("#homesnackbarSuccess").addClass("show");
                            setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 60000);
                            return;
                        }
                    }

                    summary_content =
                    '<div class="row">'+
                        '<div class="col-xl-12">';
                            if(data.errordata){
                                summary_content += '<div class="summary_page_heading">ERROR LEVEL ANALYSIS</div>';
                            } else if (data.suitedata){
                                summary_content += '<div class="summary_page_heading">SUITE LEVEL ANALYSIS</div>';
                            }
                            summary_content +=
                            '<div class="summary_page_traindata">'+trainname+' - '+build+'</div>'+
                        '</div>'+
                    '</div>';

                    if (data.severedata){
                        summary_content +=
                        '<nav>'+
                            '<div class="nav nav-tabs" id="nav-tab" role="tablist">'+
                                '<button class="nav-link active" id="nav-severelog-tab" data-bs-toggle="tab" data-bs-target="#nav-severelog" type="button" role="tab" aria-controls="nav-severelog" aria-selected="true">SEVERE LOG ANALYSIS</button>'+
                                '<button class="nav-link" id="nav-errorlog-tab" data-bs-toggle="tab" data-bs-target="#nav-errorlog" type="button" role="tab" aria-controls="nav-errorlog" aria-selected="false">ERROR LOG ANALYSIS</button>'+
                            '</div>'+
                        '</nav>';
                    }
                    if (data.severedata || data.errordata) {
                        summary_content +=
                        '<div class="tab-content" id="nav-tabContent">';
                        if(data.severedata){
                            summary_content +=
                            '<div class="tab-pane fade show active" id="nav-severelog" role="tabpanel" aria-labelledby="nav-severelog-tab">';
                                summary_content +=
                                '<table id="severelog_table">'+
                                    '<thead>'+
                                        '<tr>'+
                                            '<th>#</th>'+
                                            '<th>Log category</th>'+
                                            '<th>Counts in Train</th>'+
                                            '<th>Details</th>'+
                                        '</tr>'+
                                    '</thead>'+
                                    '<tbody>'+
                                        '<tr>'+
                                            '<td>1</td>'+
                                            '<td>New Error</td>'+
                                            '<td>'+data.severedata.new_error.length+'</td>'+
                                            '<td>';
                                            if (data.severedata.new_error.length > 0) {
                                            summary_content +=
                                                '<form action="/severe_error_triage_v2/" method="post" target="_blank">'+
                                                    '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                    '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="new_error">'+
                                                    '<button type="submit" class="btn_background severe_log_submit_btn">View</button>'+
                                                '</form>';
                                            }
                                            summary_content +=
                                            '</td>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<td>2</td>'+
                                            '<td>Bug</td>'+
                                            '<td>'+data.severedata.buggy.length+'</td>'+
                                            '<td>';
                                            if (data.severedata.buggy.length > 0) {
                                            summary_content +=
                                                '<form action="/severe_error_triage_v2/" method="post" target="_blank">'+
                                                    '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                    '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="buggy">'+
                                                    '<button type="submit" class="btn_background severe_log_submit_btn">View</button>'+
                                                '</form>';
                                            }
                                            summary_content +=
                                            '</td>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<td>3</td>'+
                                            '<td>Expected</td>'+
                                            '<td>'+data.severedata.expected.length+'</td>'+
                                            '<td>';
                                            if (data.severedata.expected.length > 0) {
                                            summary_content +=
                                                '<form action="/severe_error_triage_v2/" method="post" target="_blank">'+
                                                    '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                    '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="expected">'+
                                                    '<button type="submit" class="btn_background severe_log_submit_btn">View</button>'+
                                                '</form>';
                                            }
                                            summary_content +=
                                            '</td>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<td>4</td>'+
                                            '<td>Need Analysis</td>'+
                                            '<td>'+data.severedata.need_analysis.length+'</td>'+
                                            '<td>';
                                            if (data.severedata.need_analysis.length > 0) {
                                            summary_content +=
                                                '<form action="/severe_error_triage_v2/" method="post" target="_blank">'+
                                                    '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                    '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="need_analysis">'+
                                                    '<button type="submit" class="btn_background severe_log_submit_btn">View</button>'+
                                                '</form>';
                                            }
                                            summary_content +=
                                            '</td>'+
                                        '</tr>';
                                    summary_content +=
                                    '</tbody>'+
                                '</table>'+
                            '</div>';
                        }
                        if (data.errordata){
                            if (data.severedata){
                                summary_content +=
                                '<div class="tab-pane fade" id="nav-errorlog" role="tabpanel" aria-labelledby="nav-errorlog-tab">';
                            } else {
                                summary_content +=
                                '<div class="tab-pane fade show active" id="nav-errorlog" role="tabpanel" aria-labelledby="nav-errorlog-tab">';
                            }

                                summary_content +=
                                '<table id="errorlog_table">'+
                                    '<thead>'+
                                        '<tr>'+
                                            '<th>#</th>'+
                                            '<th>Error Signature</th>'+
                                            '<th>Suite Impacted</th>'+
                                            '<th>Overall TC Impacted</th>'+
                                            '<th>Error Count</th>'+
                                            '<th>Triage</th>'+
                                        '</tr>'+
                                    '</thead>'+
                                    '<tbody>';
                                    $.each(data.errordata, function(index,value){
                                        summary_content +=
                                        '<tr>'+
                                            '<td>'+(index+1)+'</td>'+
                                            '<td>'+value.error_sig+'</td>'+
                                            '<td>'+value.suite_impact+'</td>'+
                                            '<td>'+value.testcase_impact+'</td>'+
                                            '<td>'+value.failure_count+'</td>'+
                                            '<td>'+
                                                '<form action="/error_basis_triage_v2/" method="post" target="_blank">'+
                                                    '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                    '<input id="errorsig'+(index+1)+'" type="hidden" name="error_signature" value="'+value.error_sig+'">'+
                                                    '<button type="submit" class="btn_background severe_log_submit_btn">Triage</button>'+
                                                '</form>'+
                                            '</td>'+
                                        '</tr>';
                                    });
                                    summary_content +=
                                        '<tr>'+
                                            '<td scope="row" colspan="2" style="text-align:right;">Total</td>'+
                                            '<td style="text-align:center;">'+data.total_impacted_suite+' / '+data.total_suite_count+'</td>'+
                                            '<td>'+data.total_tc_perc+'</td>'+
                                            '<td>'+data.total_failure_count+'</td>'+
                                            '<td></td>'+
                                        '</tr>';
                                    '</tbody>'+
                                '</table>'+
                            '</div>';
                        }
                    } else if(data.suitedata) {
                        summary_content +=
                        '<div class="row">'+
                            '<div class="col-md-12 col-xl-12">'+
                                '<table id="suite_level_table">'+
                                    '<thead>'+
                                        '<tr>'+
                                            '<th>#</th>'+
                                            '<th>Suite Name</th>'+
                                            '<th>Squad</th>'+
                                            '<th>Total TC</th>'+
                                            '<th>Executed</th>'+
                                            '<th>Passed</th>'+
                                            '<th>Failed</th>'+
                                            '<th>Skipped</th>'+
                                            '<th>Pass %</th>'+
                                            '<th>Train Impact %</th>'+
                                            '<th>Suite Coverage Impact %</th>'+
                                            '<th>Triage</th>'+
                                        '</tr>'+
                                    '</thead>'+
                                    '<tbody>';
                                        $.each(data.suitedata, function(index,value){
                                        summary_content +=
                                        '<tr>'+
                                            '<td>'+(index+1)+'</td>'+
                                            '<td>'+value.suite+'</td>'+
                                            '<td>'+value.squad+'</td>'+
                                            '<td>'+value.totaltc+'</td>'+
                                            '<td>'+value.executed+'</td>'+
                                            '<td>'+value.passed+'</td>'+
                                            '<td>'+value.failure_count+'</td>'+
                                            '<td>'+value.skipped+'</td>'+
                                            '<td><span style="'+value.ccode+'color:white;padding:5px; border-radius:5px;">'+value.pass_perc+'</span></td>'+
                                            '<td>'+value.testcase_impact+'</td>'+
                                            '<td>'+value.coverage_impact+'</td>'+
                                            '<td>';
                                            if (value.failure_count > 0) {
                                                summary_content +=
                                                '<form action="/suite_basis_triage_v2/" method="post" target="_blank">'+
                                                    '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                    '<input id="suite'+(index+1)+'" type="hidden" name="suite_name" value="'+value.suite+'">'+
                                                    '<button type="submit" class="btn_background severe_log_submit_btn" id="train_suite_result_analyze_btn">Triage</button>'+
                                                '</form>';
                                            }
                                            summary_content +=
                                            '</td>'+
                                        '</tr>';
                                        });
                                    summary_content +=
                                        '<tr>'+
                                            '<td scope="row" colspan="3" style="text-align:right;">Total</th>'+
                                            '<td style="text-align:center;">'+data.total+'</td>'+
                                            '<td style="text-align:center;">'+data.executed+'</td>'+
                                            '<td>'+data.passed+'</td>'+
                                            '<td>'+data.failed+'</td>'+
                                            '<td>'+data.skipped+'</td>'+
                                            '<td>'+data.total_per+'</td>'+
                                            '<td>'+data.train_impact+'</td>'+
                                            '<td></td>'+
                                            '<td></td>'+
                                        '</tr>'+
                                    '</tbody>'+
                                '</table>'+
                            '</div>'+
                        '</div>';
                    }
                    $('#train_analyzed_result').empty();
                    $("#train_analyzed_result").append(summary_content);
                },
                error:function (xhr, ajaxOptions, thrownError){
                    if(xhr.status==404) {
                        $('#home_page_body_content').show();
                        $('#home_page_welcome_msg').show();
                        $('#train_analyzed_result').empty();
                        errorMsg = "Warning: " + xhr.responseText;
                        errorMsg += ". Please check the reports dashboard."
                        $("#homesnackbarWarningMsg").empty().append(errorMsg);
                        $("#homesnackbarWarning").addClass("show");
                        setTimeout(function() { $("#homesnackbarWarning").removeClass("show"); }, 60000);
                    }
                    if (xhr.status==500) {
                        $('#home_page_body_content').show();
                        $('#home_page_welcome_msg').show();
                        $('#train_analyzed_result').empty();
                        errorMsg = "Error:" + $($.parseHTML(xhr.responseText)).filter("title").text();
                        errorMsg += ". Please contact dev team."
                        $("#homesnackbarErrorMsg").empty().append(errorMsg);
                        $("#homesnackbarError").addClass("show");
                        setTimeout(function() { $("#homesnackbarError").removeClass("show"); }, 60000);
                    }
                }
            });
        }
    });

    $("#start_analyze_watchmen").on("click", function(){
        var wurl = $("#watchmen_log_url_input").val().trim();
        var analyze_category = $('#category_dropdown').val() || "error";
        var branch = $('#branch_name_dropdown').val() || "local";
        var trainname = $('#train_name_dropdown').val() || "magneto_dmaas_vmware_train";
        var build = $('#build_name_dropdown').val() || "watchmen-direct";
        if (!wurl) {
            $("#analyze_watchmen_error_message").removeClass("hidden").addClass("show");
            setTimeout(function() { $("#analyze_watchmen_error_message").removeClass("show"); }, 8000);
            return;
        }
        $('#train_analyzed_result').empty();
        $('#home_page_body_content').hide();
        $('#home_page_welcome_msg').hide();
        $("#train_analyzed_result").append('<div class="loader"></div>');
        $.ajax({
            url: "/analyze_watchmen_url_v2/",
            type: "POST",
            dataType: "json",
            data: JSON.stringify({
                watchmen_log_url: wurl,
                branch: branch,
                trainname: trainname,
                build: build,
                category: analyze_category,
                severe: false
            }),
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            success: function(data) {
                if (data.errordata) {
                    if ((data.errordata).length == 0){
                        $('#home_page_body_content').show();
                        $('#home_page_welcome_msg').show();
                        $('#train_analyzed_result').empty();
                        errorMsg = "Info: No errors found!";
                        $("#homesnackbarSuccess #homesnackbarSuccessMsg").empty().append(errorMsg);
                        $("#homesnackbarSuccess").addClass("show");
                        setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 60000);
                        return;
                    }
                } else if (data.suitedata) {
                    if ((data.suitedata) == 0) {
                        $('#home_page_body_content').show();
                        $('#home_page_welcome_msg').show();
                        $('#train_analyzed_result').empty();
                        errorMsg = "Info: No errors found!";
                        $("#homesnackbarSuccess #homesnackbarSuccessMsg").empty().append(errorMsg);
                        $("#homesnackbarSuccess").addClass("show");
                        setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 60000);
                        return;
                    }
                }
                var summary_content = "";
                if(data.errordata){
                    summary_content += '<div class="row"><div class="col-xl-12"><div class="summary_page_heading">ERROR LEVEL ANALYSIS</div>';
                } else if (data.suitedata){
                    summary_content += '<div class="row"><div class="col-xl-12"><div class="summary_page_heading">SUITE LEVEL ANALYSIS</div>';
                }
                summary_content += '<div class="summary_page_traindata">'+trainname+' - '+build+' (watchmen URL)</div></div></div>';
                if (data.errordata) {
                    summary_content += '<div class="tab-content"><div class="tab-pane fade show active"><table id="errorlog_table"><thead><tr><th>#</th><th>Error Signature</th><th>Suite Impacted</th><th>Overall TC Impacted</th><th>Error Count</th><th>Triage</th></tr></thead><tbody>';
                    $.each(data.errordata, function(index,value){
                        summary_content += '<tr><td>'+(index+1)+'</td><td>'+value.error_sig+'</td><td>'+value.suite_impact+'</td><td>'+value.testcase_impact+'</td><td>'+value.failure_count+'</td><td><form action="/error_basis_triage_v2/" method="post" target="_blank"><input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'"><input type="hidden" name="error_signature" value="'+value.error_sig+'"><button type="submit" class="btn_background severe_log_submit_btn">Triage</button></form></td></tr>';
                    });
                    summary_content += '<tr><td scope="row" colspan="2" style="text-align:right;">Total</td><td style="text-align:center;">'+data.total_impacted_suite+' / '+data.total_suite_count+'</td><td>'+data.total_tc_perc+'</td><td>'+data.total_failure_count+'</td><td></td></tr></tbody></table></div></div>';
                } else if (data.suitedata) {
                    summary_content += '<div class="row"><div class="col-md-12 col-xl-12"><table id="suite_level_table"><thead><tr><th>#</th><th>Suite Name</th><th>Squad</th><th>Total TC</th><th>Executed</th><th>Passed</th><th>Failed</th><th>Skipped</th><th>Pass %</th><th>Train Impact %</th><th>Suite Coverage Impact %</th><th>Triage</th></tr></thead><tbody>';
                    $.each(data.suitedata, function(index,value){
                        summary_content += '<tr><td>'+(index+1)+'</td><td>'+value.suite+'</td><td>'+value.squad+'</td><td>'+value.totaltc+'</td><td>'+value.executed+'</td><td>'+value.passed+'</td><td>'+value.failure_count+'</td><td>'+value.skipped+'</td><td><span style="'+value.ccode+'color:white;padding:5px; border-radius:5px;">'+value.pass_perc+'</span></td><td>'+value.testcase_impact+'</td><td>'+value.coverage_impact+'</td><td>';
                        if (value.failure_count > 0) {
                            summary_content += '<form action="/suite_basis_triage_v2/" method="post" target="_blank"><input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'"><input type="hidden" name="suite_name" value="'+value.suite+'"><button type="submit" class="btn_background severe_log_submit_btn">Triage</button></form>';
                        }
                        summary_content += '</td></tr>';
                    });
                    summary_content += '<tr><td scope="row" colspan="3" style="text-align:right;">Total</td><td style="text-align:center;">'+data.total+'</td><td style="text-align:center;">'+data.executed+'</td><td>'+data.passed+'</td><td>'+data.failed+'</td><td>'+data.skipped+'</td><td>'+data.total_per+'</td><td>'+data.train_impact+'</td><td></td><td></td></tr></tbody></table></div></div>';
                }
                $('#train_analyzed_result').empty();
                $("#train_analyzed_result").append(summary_content);
            },
            error:function (xhr, ajaxOptions, thrownError){
                $('#home_page_body_content').show();
                $('#home_page_welcome_msg').show();
                $('#train_analyzed_result').empty();
                if(xhr.status==404) {
                    errorMsg = "Warning: " + xhr.responseText;
                    $("#homesnackbarWarningMsg").empty().append(errorMsg);
                    $("#homesnackbarWarning").addClass("show");
                    setTimeout(function() { $("#homesnackbarWarning").removeClass("show"); }, 60000);
                }
                if (xhr.status==500) {
                    errorMsg = "Error:" + $($.parseHTML(xhr.responseText)).filter("title").text();
                    $("#homesnackbarErrorMsg").empty().append(errorMsg);
                    $("#homesnackbarError").addClass("show");
                    setTimeout(function() { $("#homesnackbarError").removeClass("show"); }, 60000);
                }
            }
        });
    });

    $("input[name='severetype']").change(function(){
        var form_id = $(this).parents("form[name='submitSevereSolution']").attr("id");
        var cat_val = $(this).val();
        if (cat_val == 'buggy'){
            $('#'+form_id+' #comments').val('');
            $("#"+form_id+" .server_log_comment .err_bug_modal_error").removeClass("modal_submit_error_msg_show");
            $('#'+form_id+' .severe_log_bug').removeClass('display_none');
            $('#'+form_id+' .server_log_comment').addClass('display_none');
        } else if (cat_val == 'expected' || cat_val == 'need_analysis') {
            $('#'+form_id+' #bugid').val('');
            $("#"+form_id+" .severe_log_bug .err_bug_modal_error").removeClass("modal_submit_error_msg_show");
            $("#"+form_id+" .severe_log_bug .server_log_comment").removeClass("modal_submit_error_msg_show");
            $('#'+form_id+' .severe_log_bug').addClass('display_none');
            $('#'+form_id+' .server_log_comment').removeClass('display_none');
        }
    });

    $('form[name="submitSevereSolution"]').on("submit",function(e){
        e.preventDefault();
        var form_id = $(this).attr("id");
        var modalnumber = form_id.match(/\d+/);
        var err_category = $("#"+form_id+" input[name='severetype']:checked").val();
        var err_sig = $("#"+form_id+" #severesignature").val();
        var bug_id = $("#"+form_id+" #bugid").val();
        var comments = $("#"+form_id+" #comments").val();
        var form_values_are_cleaned = true
        if (typeof err_category == 'undefined') {
            $("#"+form_id+" .err_cat_modal_error").addClass("modal_submit_error_msg_show");
            form_values_are_cleaned = false;
            setTimeout(function() { $("#"+form_id+" .err_cat_modal_error").removeClass("modal_submit_error_msg_show"); }, 10000);
        }
        if (err_category == 'buggy' && bug_id == "") {
            $("#"+form_id+" .err_bug_modal_error").addClass("modal_submit_error_msg_show");
            form_values_are_cleaned = false;
            setTimeout(function() { $("#"+form_id+" .err_bug_modal_error").removeClass("modal_submit_error_msg_show"); }, 10000);
        }
        if(err_category == 'buggy' && bug_id != "") {
            var re = new RegExp("^(ENG|ENGOPS|DEVXRQ)-[0-9]{3,8}$");
            if (!re.test(bug_id)){
                $("#"+form_id+" .err_valid_bug_modal_error").addClass("modal_submit_error_msg_show");
                form_values_are_cleaned = false;
                setTimeout(function() { $("#"+form_id+" .err_valid_bug_modal_error").removeClass("modal_submit_error_msg_show"); }, 10000);
            }
        }
        if ((err_category == 'expected' || err_category == 'need_analysis') && comments == '') {
            $("#"+form_id+" .err_cmt_modal_error").addClass("modal_submit_error_msg_show");
            form_values_are_cleaned = false;
            setTimeout(function() { $("#"+form_id+" .err_cmt_modal_error").removeClass("modal_submit_error_msg_show"); }, 10000);
        }
        if (form_values_are_cleaned){
            $.ajax({
                    url: "/submit_severe_solution/",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        err_category: err_category,
                        cleaned_err_sig: err_sig,
                        bug_id: bug_id,
                        comments: comments
                    }),
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    success: function(data) {
                        $('#modelSevereLogSubmit'+modalnumber).modal('hide');
                        succMsg = "Successfully Marked the severe error..";
                        $("#"+form_id+"SevereTable").remove();
                        $("#homesnackbarSuccess").empty().append(succMsg);
                        $("#homesnackbarSuccess").addClass("show");
                        setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 10000);
                    },
                    error:function (xhr, ajaxOptions, thrownError){
                        if (xhr.status==500) {
                            errorMsg = "Error:" + $($.parseHTML(xhr.responseText)).filter("title").text();
                            errorMsg += ". Please contact dev team."
                            $("#homesnackbarError").empty().append(errorMsg);
                            $("#homesnackbarError").addClass("show");
                            setTimeout(function() { $("#homesnackbarError").removeClass("show"); }, 10000);
                        }
                    }
            });
        }
    });
});