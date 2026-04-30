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
function openNav() {
    document.getElementById("dasssidebar").style.width = "250px";
    document.getElementById("train_analyzed_result").style.marginLeft = "250px";
}

function closeNav() {
    document.getElementById("dasssidebar").style.width = "0";
    document.getElementById("train_analyzed_result").style.marginLeft = "0";
}
$(document).ready(function() {
    $('#train_name_dropdown').select2({ placeholder: "Train Name*"});
    $('#branch_name_dropdown').select2({ placeholder: "Branch*" });
    $('#build_name_dropdown').select2({ placeholder: "Build*" });
    $('#category_dropdown').select2({ placeholder: "Error/Suite*" });
    $('#squad_dropdown').select2({ placeholder: "Squad" });
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
            }
        });
    });

    $("#home_page_analyze_btn").on("click", function(){
        var branch = $('#branch_name_dropdown').val();
        var trainname = $("#train_name_dropdown").val();
        var build = $('#build_name_dropdown').val();
        var analyze_category = $('#category_dropdown').val();
        var squad = $('#squad_dropdown').val();
        var sidemenu_status = $('#side_menu_open_button').attr('data-navstatus');
        var severe_log = $("#withseverelog").is(':checked')
        if(branch=="" || trainname=="" || build=="" ||  analyze_category==""){
            $("#error_message").removeClass("hidden");
            $("#error_message").addClass("show");
            setTimeout(function() { $("#error_message").removeClass("show"); }, 10000);
        }
        if(squad==""){
            squad = "all"
        }
        $('#train_analyzed_result').empty();
         $("#severelog_analyzed_result").empty();
        if(branch!="" && trainname!="" && build!="" && analyze_category!=""){
            if (sidemenu_status == 'open') {
                $('#dasssidebar').css('width','0px');
                $('#train_analyzed_result').css('margin-left','0px');
                $('#side_menu_open_button').attr('data-navstatus','close');
            }
            $("#SearchEngineSol").empty();
            $('.home_page_optimal_solution_section').css("height","0vh");
            $("#home_page_welcome_msg").remove();
            $("#daas_dashboar_metrics").remove();
            $("#GetStartButtonDiv").remove();
            $("#error_message").removeClass("show");
            $("#error_message").addClass("hidden");
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
                    severe: severe_log
                }),
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                success: function(data) {
                    var sidemenu_status = $('#side_menu_open_button').attr('data-navstatus');
                    if (sidemenu_status == 'open') {
                        $('#dasssidebar').css('width','0px');
                        $('#train_analyzed_result').css('margin-left','0px');
                        $(this).attr('data-navstatus','close');
                    }
                    $('#train_analyzed_result').empty();
                    $("#severelog_analyzed_result").empty();
                    if (data.errordata) {
                        if ((data.errordata).length == 0){
                            $('#train_analyzed_result').empty();
                            errorMsg = "Info: No errors found!";
                            $("#homesnackbarSuccess").empty().append(errorMsg);
                            $("#homesnackbarSuccess").addClass("show");
                            setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 10000);
                            return;
                        }
                    } else if (data.suitedata) {
                        if ((data.suitedata) == 0) {
                            $('#train_analyzed_result').empty();
                            errorMsg = "Info: No errors found!";
                            $("#homesnackbarSuccess").empty().append(errorMsg);
                            $("#homesnackbarSuccess").addClass("show");
                            setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 10000);
                            return;
                        }
                    }
                    if(data.errordata){
                        html = '<table class="table table-striped table-bordered" id="indextable">'+
                                    '<thead id="indextable_head">'+
                                        '<tr>'+
                                            '<th id="home_table_name" colspan="6"><h2>Error Analysis</h2></th>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th id="home_table_name" colspan="12">'+
                                                '<p>'+trainname+'  -  '+build+'</p>'+
                                            '</th>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th scope="col" style="width:2%">S.No</th>'+
                                            '<th scope="col" style="width:60%">Error Signature</th>'+
                                            '<th scope="col" style="width:7%">Suite Impacted</th>'+
                                            '<th scope="col" style="width:7%">Overall Testcases Impacted %</th>'+
                                            '<th scope="col" style="width:5%">Error Count</th>'+
                                            '<th scope="col" style="width:5%">Triage</th>'+
                                        '</tr>'+
                                    '</thead>'+
                                    '<tbody id="indextable_body">'
                        $.each(data.errordata, function(index,value){
                            html += '<tr>'+
                                        '<th scope="row">'+(index+1)+'</th>'+
                                        '<td style="text-align: left">'+value.error_sig+'</td>'+
                                        '<td>'+value.suite_impact+'</td>'+
                                        '<td>'+value.testcase_impact+'</td>'+
                                        '<td>'+value.failure_count+'</td>'+
                                        '<td>'+
                                            '<form action="/error_basis_triage/" method="post" target="_blank">'+
                                            '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                            '<input id="errorsig'+(index+1)+'" type="hidden" name="error_signature" value="'+value.error_sig+'">'+
                                            '<button type="submit" class="btn btn-info" id="train_result_table_analyze_btn">Triage</button>'+
                                            '</form>'
                                        '</td>'+
                                    '</tr>';
                        });
                        html += '<tr>'+
                                    '<th scope="row" colspan="2">Total</th>'+
                                    '<td>'+data.total_impacted_suite+' / '+data.total_suite_count+'</td>'+
                                    '<td>'+data.total_tc_perc+'</td>'+
                                    '<td>'+data.total_failure_count+'</td>'+
                                    '<td></td>'+
                                '</tr>';
                        html += '</tbody></table>';
                        $("#train_analyzed_result").append(html);
                        if (data.severedata){
                            shtml = '<table class="table table-striped table-bordered" id="indextable">'+
                                    '<thead id="severe_head">'+
                                        '<tr>'+
                                            '<th id="home_table_name" colspan="6"><h2>Severe Log Analysis</h2></th>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th scope="col" style="width:10%">S.No</th>'+
                                            '<th scope="col" style="width:60%">Severe Log Category</th>'+
                                            '<th scope="col" style="width:15%">Error Counts in Train</th>'+
                                            '<th scope="col" style="width:15%">View Details</th>'+
                                        '</tr>'+
                                    '</thead>'+
                                    '<tbody id="severe_body">'+
                                        '<tr>'+
                                            '<th scope="row">1</th>'+
                                            '<td style="text-align: left">New Error</td>'+
                                            '<td>'+data.severedata.new_error.length+'</td>'+
                                            '<td>';
                            if (data.severedata.new_error.length > 0) {
                                shtml +=    '<form action="/severe_error_triage/" method="post" target="_blank">'+
                                                '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="new_error">'+
                                                '<button type="submit" class="btn btn-info" id="train_result_table_analyze_btn">View</button>'+
                                            '</form>';
                            }

                                shtml +=    '</td>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th scope="row">2</th>'+
                                            '<td style="text-align: left">Buggy</td>'+
                                            '<td>'+data.severedata.buggy.length+'</td>'+
                                            '<td>';
                            if (data.severedata.buggy.length >0) {
                                shtml += '<form action="/severe_error_triage/" method="post" target="_blank">'+
                                                '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="buggy">'+
                                                '<button type="submit" class="btn btn-info" id="train_result_table_analyze_btn">View</button>'+
                                          '</form>';
                            }

                                shtml +=  '</td>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th scope="row">3</th>'+
                                            '<td style="text-align: left">Expected</td>'+
                                            '<td>'+data.severedata.expected.length+'</td>'+
                                            '<td>';
                            if (data.severedata.expected.length > 0) {
                                shtml += '<form action="/severe_error_triage/" method="post" target="_blank">'+
                                                '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="expected">'+
                                                '<button type="submit" class="btn btn-info" id="train_result_table_analyze_btn">View</button>'+
                                          '</form>';
                            }

                                shtml +=   '</td>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th scope="row">4</th>'+
                                            '<td style="text-align: left">Need Analysis</td>'+
                                            '<td>'+data.severedata.need_analysis.length+'</td>'+
                                            '<td>';
                            if (data.severedata.need_analysis.length > 0) {
                                shtml += '<form action="/severe_error_triage/" method="post" target="_blank">'+
                                                '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                                '<input id="severeerrorsig" type="hidden" name="severeerrorsig" value="need_analysis">'+
                                                '<button type="submit" class="btn btn-info" id="train_result_table_analyze_btn">View</button>'+
                                          '</form>';
                            }

                                shtml +=   '</td>'+
                                        '</tr>'+
                                    '</tbody></table>';
                            $("#severelog_analyzed_result").append(shtml);
                        }
                    } else if(data.suitedata) {
                        html = '<table class="table table-striped table-bordered" id="indextable">'+
                                    '<thead id="indextable_head">'+
                                        '<tr>'+
                                            '<th id="home_table_name" colspan="12"><h2>Suite level Analysis</h2></th>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th id="home_table_name" colspan="12">'+
                                                '<p>'+trainname+'  -  '+build+'</p>'+
                                            '</th>'+
                                        '</tr>'+
                                        '<tr>'+
                                            '<th scope="col" style="width:3%">S.No</th>'+
                                            '<th scope="col" style="width:30%">Suite Name</th>'+
                                            '<th scope="col" style="width:10%">Squad</th>'+
                                            '<th scope="col" style="width:5%">Total TC</th>'+
                                            '<th scope="col" style="width:5%">Executed</th>'+
                                            '<th scope="col" style="width:5%">Passed</th>'+
                                            '<th scope="col" style="width:5%">Failed</th>'+
                                            '<th scope="col" style="width:5%">Skipped</th>'+
                                            '<th scope="col" style="width:5%">Pass %</th>'+
                                            '<th scope="col" style="width:11%">Train Impact %</th>'+
                                            '<th scope="col" style="width:11%">Suite Coverage Impact %</th>'+
                                            '<th scope="col" style="width:5%">Triage</th>'+
                                        '</tr>'+
                                    '</thead>'+
                                    '<tbody id="indextable_body">'
                        $.each(data.suitedata, function(index,value){
                            if (value.failure_count > 0) {
                                triage_btn = '<form action="/suite_basis_triage/" method="post" target="_blank">'+
                                            '<input type="hidden" name="csrfmiddlewaretoken" value="'+getCookie("csrftoken")+'">'+
                                            '<input id="suite'+(index+1)+'" type="hidden" name="suite_name" value="'+value.suite+'">'+
                                            '<button type="submit" class="btn btn-info" id="train_suite_result_analyze_btn">Triage</button>'+
                                            '</form>'
                            } else {
                                triage_btn = ''
                            }
                            html += '<tr>'+
                                        '<th scope="row">'+(index+1)+'</th>'+
                                        '<td style="text-align: left">'+value.suite+'</td>'+
                                        '<td>'+value.squad+'</td>'+
                                        '<td>'+value.totaltc+'</td>'+
                                        '<td>'+value.executed+'</td>'+
                                        '<td>'+value.passed+'</td>'+
                                        '<td>'+value.failure_count+'</td>'+
                                        '<td>'+value.skipped+'</td>'+
                                        '<td style="'+value.ccode+'color:white;">'+value.pass_perc+'</td>'+
                                        '<td>'+value.testcase_impact+'</td>'+
                                        '<td>'+value.coverage_impact+'</td>'+
                                        '<td>'+triage_btn+'</td>'+
                                    '</tr>';
                        });
                        html += '<tr>'+
                                        '<th scope="row" colspan="3">Total</th>'+
                                        '<td>'+data.total+'</td>'+
                                        '<td>'+data.executed+'</td>'+
                                        '<td>'+data.passed+'</td>'+
                                        '<td>'+data.failed+'</td>'+
                                        '<td>'+data.skipped+'</td>'+
                                        '<td>'+data.total_per+'</td>'+
                                        '<td>'+data.train_impact+'</td>'+
                                        '<td></td>'+
                                        '<td></td>'+
                                    '</tr>';
                        html += '</tbody></table>';
                        $("#train_analyzed_result").append(html);

                    }
                },
                error:function (xhr, ajaxOptions, thrownError){
                    if(xhr.status==404) {
                        $('#train_analyzed_result').empty();
                        errorMsg = "Warning: " + xhr.responseText;
                        errorMsg += ". Please check the reports dashboard."
                        $("#homesnackbarWarning").empty().append(errorMsg);
                        $("#homesnackbarWarning").addClass("show");
                        setTimeout(function() { $("#homesnackbarWarning").removeClass("show"); }, 10000);
                    }
                    if (xhr.status==500) {
                        $('#train_analyzed_result').empty();
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

    $('#side_menu_open_button').on('click',function(){
        var sidemenu_status = $(this).attr('data-navstatus');
        if (sidemenu_status == 'close'){
            $('#dasssidebar').css('width','250px');
            $('#train_analyzed_result').css('margin-left','250px');
            $(this).attr('data-navstatus','open');
        }else if (sidemenu_status == 'open') {
            $('#dasssidebar').css('width','0px');
            $('#train_analyzed_result').css('margin-left','0px');
            $(this).attr('data-navstatus','close');
        }
    });

    $('#GetStartButton').on('click',function(){
        var sidemenu_status = $('#side_menu_open_button').attr('data-navstatus');
        if (sidemenu_status != 'open'){
            $('#dasssidebar').css('width','250px');
            $('#train_analyzed_result').css('margin-left','250px');
            $('#side_menu_open_button').attr('data-navstatus','open');
        }
    });

    $('#custom_navbar_logo_img').on('click',function(){
        window.location = "/"
    });

    $('form[name="submitOptimalSolition"]').on("submit",function(e){
        e.preventDefault();
        var os_form_id = $(this).attr("id");
        var modalnumber = os_form_id.match(/\d+/);
        var email_pattern = /^\b[A-Z0-9._%-]+@cohesity.com\b$/i
        var optimal_solution_val = $("#"+os_form_id+" #optimalsolution").val();
        var email_val = $("#"+os_form_id+" #emailaddress").val();
        var category_val = $("#"+os_form_id+" #errorcategory").val();
        var common_sol_val = $("#"+os_form_id+" #commonsolution").is(':checked');
        var cleaned_err_sig = $("#"+os_form_id+" #cleaned_error_sig").val();
        var cleaned_err_msg = $("#"+os_form_id+" #cleaned_error_msg").val();
        var form_values_are_cleaned = true
        if (cleaned_err_sig == "" || cleaned_err_msg == "") {
            $("#"+os_form_id+" .os_invalid_server_failure").addClass("os_submit_error_msg_show");
            form_values_are_cleaned = false;
            setTimeout(function() { $("#"+os_form_id+" .os_invalid_server_failure").removeClass("os_submit_error_msg_show"); }, 10000);
        }
        if (optimal_solution_val == "") {
            $("#"+os_form_id+" .os_invalid_optimal_solution").addClass("os_submit_error_msg_show");
            form_values_are_cleaned = false
            setTimeout(function() { $("#"+os_form_id+" .os_invalid_optimal_solution").removeClass("os_submit_error_msg_show"); }, 10000);
        }
        if (email_val == "" || !email_pattern.test(email_val)){
            $("#"+os_form_id+" .os_invalid_email").addClass("os_submit_error_msg_show");
            form_values_are_cleaned = false
            setTimeout(function() { $("#"+os_form_id+" .os_invalid_email").removeClass("os_submit_error_msg_show"); }, 10000);
        }
        if (category_val == "") {
            $("#"+os_form_id+" .os_invalid_error_category").addClass("os_submit_error_msg_show");
            form_values_are_cleaned = false
            setTimeout(function() { $("#"+os_form_id+" .os_invalid_error_category").removeClass("os_submit_error_msg_show"); }, 10000);
        }
        if (form_values_are_cleaned) {
            $("#"+os_form_id+" button[type='submit']").attr("disabled","disabled")
            $.ajax({
                url: "/submit_optimal_solution/",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    cleaned_err_msg: cleaned_err_msg,
                    cleaned_err_sig: cleaned_err_sig,
                    optimal_solution: optimal_solution_val,
                    email_addr: email_val,
                    category:category_val,
                    common_solution: common_sol_val}),
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                success: function(data) {
                    $('#modelSubmitSolution'+modalnumber).modal('hide');
                    succMsg = "Successfully submitted your solution. It will be under review.";
                    $("#homesnackbarSuccess").empty().append(succMsg);
                    $("#homesnackbarSuccess").addClass("show");
                    setTimeout(function() { $("#homesnackbarSuccess").removeClass("show"); }, 10000);
                },
                error:function (xhr, ajaxOptions, thrownError){
                    if (xhr.status==500) {
                        $('#modelSubmitSolution'+modalnumber).modal('hide');
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

    $('#SearchSolButton').on('click',function(){
        var error_input = $('#SearchInput').val();
        if (error_input == "") {
            errorMsg = "Please specify the error message for search"
            $("#homesnackbarError").empty().append(errorMsg);
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
                    $("#SearchEngineSol").empty();
                    $('.home_page_optimal_solution_section').css("height","30vh")
                    $("#SearchEngineSol").append(data.solution)
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