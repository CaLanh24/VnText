using System.IO;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

/// <summary>Owner report on 0.1.35 (Sửa CSV + Tạo patch on a real Ren'Py game), one named check per reported issue; synthetic rows only.</summary>
internal static partial class Program
{
    private static List<CsvEditorRow> Owner0136Rows() => new()
    {
        new CsvEditorRow { Index = 0, Key = "u1", SourceText = "Hello there." },
        new CsvEditorRow { Index = 1, Key = "u2", SourceText = "Good night." },
        new CsvEditorRow { Index = 2, Key = "t1", SourceText = "Chapter 1", Translation = "Chương 1" },
        new CsvEditorRow { Index = 3, Key = "r1", SourceText = "Hold on tight!", IsReviewOnly = true },
        new CsvEditorRow { Index = 4, Key = "r2", SourceText = "Disabled label", Translation = "Nhãn tắt", IsReviewOnly = true },
        new CsvEditorRow { Index = 5, Key = "x1", SourceText = "[page]", IsTechnical = true },
    };

    private static CsvEditorValidateResult Owner0136Validation(Dictionary<string, string> issues, Dictionary<string, string>? actions = null, Dictionary<string, string>? candidates = null)
    {
        var display = issues.ToDictionary(kv => kv.Key, kv => kv.Value switch
        {
            "human_review" => "Bản dịch máy đang chờ bạn duyệt",
            "review_only" => "Không ghi được vào game: chưa tìm được vị trí ghi an toàn cho dòng này, nên Tạo patch sẽ bỏ qua (bản dịch vẫn được lưu)",
            "mt_blocked" => "Máy dịch không cho ra bản dịch an toàn cho dòng này; cần tự dịch",
            _ => kv.Value,
        });
        return new CsvEditorValidateResult(true, "ok", issues.Count, new Dictionary<string, int>(), issues, display, 1, issues.Count, 0, false,
            IssuesAction: actions ?? new Dictionary<string, string>(), ReviewCandidates: candidates ?? new Dictionary<string, string>());
    }

    private static MainViewModel Owner0136Vm(List<CsvEditorRow> rows)
    {
        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        vm.TestLoadCsvRows(Path.Combine(TestTempRoot(), "owner0136", "translation.csv"), rows, "ok");
        return vm;
    }

    private static void Owner0136_Issue1_SelectUntranslatedAndReviewCheckEveryMatchingRow()
    {
        var rows = Owner0136Rows();
        using var vm = Owner0136Vm(rows);
        vm.TestApplyValidation(Owner0136Validation(new() { ["r1"] = "human_review", ["r2"] = "review_only" }));
        vm.CsvFilterMode = CsvFilterModes.Errors;                                    // a filter that hides the untranslated rows
        Require(vm.CsvSelectUntranslatedCommand.CanExecute(null), "Chọn dòng chưa dịch is available with a document open");
        vm.CsvSelectUntranslatedCommand.Execute(null);
        AssertEqual(3, vm.CsvCheckedCount);                                          // u1, u2, r1 (empty); never the technical row
        Require(rows.Where(r => r.IsSelected).All(r => r.NeedsTranslation), "only untranslated rows are checked");
        AssertEqual(CsvFilterModes.Untranslated, vm.CsvFilterMode);                 // the checked rows are the ones shown
        vm.CsvSelectReviewCommand.Execute(null);
        AssertEqual(2, vm.CsvCheckedCount);
        Require(rows.Single(r => r.Key == "r1").IsSelected && rows.Single(r => r.Key == "r2").IsSelected, "both review rows are checked");
        AssertEqual(CsvFilterModes.ReviewOnly, vm.CsvFilterMode);
    }

    private static void Owner0136_Issue2_SavedManualTranslationDropsTheStaleReviewStatus()
    {
        var rows = Owner0136Rows();
        using var vm = Owner0136Vm(rows);
        var row = rows.Single(r => r.Key == "r1");
        vm.TestApplyValidation(Owner0136Validation(new() { ["r1"] = "mt_blocked" }));
        Require(row.IsReviewOnly && row.HasIssue, "before: in review");
        row.Translation = "Bám chặt vào!";
        // after Save the ledger no longer holds r1: validation reports no issue for it.  The flag read at load must not keep "review".
        vm.TestApplyValidation(Owner0136Validation(new()));
        Require(!row.IsReviewOnly, "the saved row is no longer 'Cần xem lại'");
        AssertEqual("", row.IssueLabel);
        AssertEqual(UiText.Translate("Đã dịch"), row.IssueShort);
        Require(!row.IssueShort.Contains("đường ghi"), "the old unexplained phrase is gone");
        AssertEqual("Không ghi được vào game", CsvEditorRow.ShortenIssue("Không ghi được vào game: chưa tìm được vị trí ghi an toàn cho dòng này, nên Tạo patch sẽ bỏ qua (bản dịch vẫn được lưu)"));
        AssertEqual("Bấm Lưu", CsvEditorRow.ShortenIssue("Đã dịch — bấm Lưu để đưa dòng này vào patch"));
    }

    private static void Owner0136_Issue3_SelectedTranslateResultNamesWhatHappenedToEachRow()
    {
        var evt = WorkerEvent.FromJson("""{"type":"complete","ok":true,"operation_scope":"selected_rows","summary":"Đã dịch và lưu 0; bỏ qua 0; chờ bạn duyệt 3; chưa dịch được 0 dòng. Xem lý do từng dòng trong Nhật ký.","selected_outcomes":[{"key":"a","status":"review","reason":"manual_review_protected","message":"bản dịch máy đang chờ bạn duyệt: bấm 'Chấp nhận đề xuất' hoặc tự sửa rồi Lưu"},{"key":"b","status":"review","reason":"manual_review_protected","message":"bản dịch máy đang chờ bạn duyệt: bấm 'Chấp nhận đề xuất' hoặc tự sửa rồi Lưu"},{"key":"c","status":"failed","reason":"translation_not_saved","message":"máy dịch không cho ra bản dịch an toàn; hãy tự gõ bản dịch rồi Lưu"}]}""")!;
        AssertEqual("selected_rows", evt.OperationScope);
        AssertEqual(3, evt.SelectedMessages.Count);
        var text = MainViewModel.SelectedTranslateText(evt);
        Require(text.Contains("chờ bạn duyệt 3"), "the counts are shown: " + text);
        Require(text.Contains("• 2 dòng: bản dịch máy đang chờ bạn duyệt"), "each distinct outcome with its row count: " + text);
        Require(text.Contains("• 1 dòng: máy dịch không cho ra bản dịch an toàn"), "a row that stayed empty says why: " + text);
        Require(!text.Contains("Dịch tự động hoàn tất"), "never the generic 'done' when nothing may have changed");
    }

    private static void Owner0136_Issue4_FocusedReviewRowShowsReasonActionAndAcceptableProposal()
    {
        var rows = Owner0136Rows();
        using var vm = Owner0136Vm(rows);
        vm.TestApplyValidation(Owner0136Validation(new() { ["r1"] = "human_review", ["r2"] = "review_only" },
            new() { ["r1"] = "Bấm 'Chấp nhận đề xuất' để dùng bản dịch máy, hoặc tự sửa rồi Lưu. Hoặc 'Bỏ qua dòng này'.", ["r2"] = "Không cần làm gì: Patch bỏ qua dòng này." },
            new() { ["r1"] = "Bám chặt vào!" }));
        var r1 = rows.Single(r => r.Key == "r1");
        vm.UpdateCsvEditorSelection(new[] { r1 });
        Require(vm.CsvFocusedIssueVisible, "the reason strip is shown for a review row");
        Require(vm.CsvFocusedIssueReason.Contains("chờ bạn duyệt"), vm.CsvFocusedIssueReason);
        Require(vm.CsvFocusedIssueAction.Contains("Chấp nhận đề xuất"), vm.CsvFocusedIssueAction);
        Require(vm.CsvFocusedHasCandidate && vm.CsvFocusedCandidate.Contains("Bám chặt vào!"), vm.CsvFocusedCandidate);
        Require(vm.CsvAcceptCandidateCommand.CanExecute(null), "Chấp nhận đề xuất is available");
        Require(vm.CsvSkipFocusedCommand.CanExecute(null), "Bỏ qua dòng này is available");
        vm.UpdateCsvEditorSelection(new[] { rows.Single(r => r.Key == "r2") });
        Require(vm.CsvFocusedIssueAction.Contains("Không cần làm gì"), vm.CsvFocusedIssueAction);
        Require(!vm.CsvFocusedHasCandidate && !vm.CsvAcceptCandidateCommand.CanExecute(null), "no proposal, no accept");
        vm.UpdateCsvEditorSelection(new[] { rows.Single(r => r.Key == "t1") });
        Require(!vm.CsvFocusedIssueVisible, "a ready row shows no strip");
    }

    private static void Owner0136_Issue5_PatchSkippedFilterAndListMatchTheGate()
    {
        var rows = Owner0136Rows();
        using var vm = Owner0136Vm(rows);
        vm.TestApplyValidation(Owner0136Validation(new() { ["r1"] = "human_review", ["r2"] = "review_only" }));
        vm.CsvFilterMode = CsvFilterModes.PatchSkipped;
        AssertEqual(4, vm.CsvEditorVisibleCount);                                     // u1, u2, r1, r2 — not the ready row, not the technical row
        var items = new List<PatchSkippedItem>
        {
            new("u1", "Hello there.", "", "no_translation", "Chưa có bản dịch trong translation.csv", "Dịch dòng này rồi bấm Lưu."),
            new("u2", "Good night.", "", "no_translation", "Chưa có bản dịch trong translation.csv", "Dịch dòng này rồi bấm Lưu."),
            new("r2", "Disabled label", "Nhãn tắt", "review_only", "Không ghi được vào game", "Không cần làm gì."),
        };
        var text = PatchIssueText.FormatList(items, truncated: false, userExcluded: 39, outsideCsv: 17);
        Require(text.Contains("Chưa có bản dịch trong translation.csv — 2 câu"), text);
        Require(text.Contains("Cách xử lý: Dịch dòng này rồi bấm Lưu."), text);
        Require(text.Contains("• Hello there."), text);
        Require(text.Contains("39 dòng bạn đã xóa") && text.Contains("17 dòng chỉ để xem lại"), "deleted and outside-CSV rows are named apart, not counted: " + text);
    }

    private static void Owner0136_Issue6_PatchFailureIsExplainedInPlaceWithBugReportButtons()
    {
        var explained = PatchIssueText.Explain("Ren'Py dialogue mapping conflict: swing_action_d4ab5336");
        Require(explained.Contains("Nguyên nhân:") && explained.Contains("Cách xử lý:"), explained);
        Require(explained.Contains("…_d4ab5336") && !explained.Contains("swing_action"), "the unit id is masked: " + explained);
        AssertEqual("(đã che)", PatchIssueText.MaskUnitId("no-hash"));
        Require(PatchIssueText.Explain("something new").Contains("Gửi báo lỗi"), "an unknown failure offers the report");
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        Require(!vm.HasPatchError, "no error before a build");
        vm.RecordPatchFailure("Ren'Py dialogue mapping conflict: swing_action_d4ab5336");
        Require(vm.HasPatchError && vm.PatchErrorText.Contains("…_d4ab5336"), vm.PatchErrorText);
        vm.ClearPatchFailure();
        Require(!vm.HasPatchError, "cleared by the next build");
        var xaml = File.ReadAllText(Path.Combine(RepoRoot(), "wpf_app", "VNText.Studio.App", "MainWindow.xaml"));
        var panel = xaml[xaml.IndexOf("x:Name=\"PatchErrorPanel\"", StringComparison.Ordinal)..];
        panel = panel[..panel.IndexOf("</Border>", StringComparison.Ordinal)];
        Require(panel.Contains("x:Name=\"PatchErrorSendButton\"") && panel.Contains("{Binding SendBugReportCommand}"), "Gửi báo lỗi sits on the error panel");
        Require(panel.Contains("{Binding CreateBugReportCommand}"), "Tạo gói báo lỗi sits on the error panel");
        Require(panel.Contains("{Binding HasPatchError"), "the panel follows the failure");
    }
}
