# Ghosts of November — shared engineering brief for milestone builders (M3–M7)

You are one of several engineers building milestones of a UE 5.7 C++ game plugin **in sequence**. Earlier milestones are already in the repo. Later milestones come after you. Nobody can compile Unreal here: the user builds ONCE on Windows (UE 5.7, MSVC, shadowing = error, UHT -WarningsAsErrors) after all milestones. **A single compile error blocks the whole delivery**, so compile safety beats feature count.

## Repository
- Root: `/tmp/hoplite/workspace/.hoplite/work/must-main` (a git repo; the previous milestone is committed. Do NOT commit; the coordinator does).
- Read first: `README.md`, the top of `CHANGELOG.md`, `Docs/Brief/GAME_BRIEF.md`, the relevant sections of `Docs/Brief/design/DESIGN_DOC_AR.md` (source of truth for story/history), `Docs/Brief/ASSET_MANIFEST.md`.
- Plugin: `Plugins/GhostsOfNovember/` (`.uplugin`, `Source/GoN<Module>/{Public,Private}`, `Data/`).
- Pure logic: `Source/GoN<Module>/Public/Logic/*.h`, `Private/Logic/*.cpp`, tests in `Private/Tests/Logic/*.cpp`.
- Standalone tests: `bash Tools/run_logic_tests.sh` (two builds: strict `-Wshadow -Werror -Wfloat-conversion -fno-exceptions -fno-rtti`, and a per-module unity build with UE/Windows macro names force-included from `Tools/LogicTests/ue_macro_shim.h`). `--validate` prints narrative data issues. Add every module that has Logic to `GON_MODULES` in `Tools/LogicTests/CMakeLists.txt` (in dependency order).
- `Reference/AAAWeapons/` is the old prototype: read it, port from it, NEVER edit it.
- Fonts already bundled: `Plugins/GhostsOfNovember/Data/Fonts/{Amiri-Regular,Amiri-Bold,CourierPrime-Regular,CourierPrime-Bold}.ttf` (OFL).

## Conventions (follow the existing code exactly)
- Tabs, Unreal naming (F/U/A/E/I prefixes, b for bools), braces on their own lines, `// comments` brief, only for non-obvious intent.
- Pure logic: namespace `GoN::<System>` (e.g. `GoN::Stealth`), no Unreal headers, no exceptions/RTTI, `double` maths, explicit `static_cast` for double↔float/int, C++20 std only.
- Pure tests: `GON_LOGIC_TEST("<Module>.<Group>.<Name>", <UniqueId>)` + `GON_EXPECT`, `GON_EXPECT_EQ`, `GON_REQUIRE` from `Logic/GoNLogicTest.h`, wrapped in `#if GON_WITH_LOGIC_TESTS`. The name must start with the module tag (`Stealth.`, `AI.`, …). The Id must be unique **within the module** (unity builds). Each module exposes its cases to Unreal with one file `Private/Tests/GoN<Module>AutomationTests.cpp` containing `GON_IMPLEMENT_LOGIC_AUTOMATION_TESTS(FGoN<Module>LogicTests, "GoN.<Module>.Logic", "<Module>.")` (see `GoNBlockout/Private/Tests/GoNBlockoutAutomationTests.cpp`). Data tests read through `GoN::LogicTest::DataAccess()`.
- JSON: use the existing pure parser `Logic/GoNJson.h` (GoNCore). Narrative JSON loader: `GoNNarrative/Private/Logic/GoNNarrativeLoader.cpp`.
- Strings across the boundary: `GoNStringConv.h` (`ToFString`, `ToStd`).
- Logs: each module has `LogGoN<System>`; prefix messages `GoN <System>: ...`.
- Console: `gon.<system>.*`. Use `TAutoConsoleVariable` / `FAutoConsoleCommand` / `FAutoConsoleCommandWithWorldAndArgs` at file scope with globally unique C++ variable names (e.g. `GGoNStealthDebugCVar`).
- Debug overlays: `UDebugDrawService::Register(TEXT("Game"), FDebugDrawDelegate::CreateUObject(...))` like `GoNNarrativeSubsystem.cpp`. Canvas text is ASCII only (ids, French without problem, numbers). **Arabic text is NEVER drawn with Canvas/DrawText**; it goes through the shaped Slate path (M4 builds it).
- Tunables: either a `UDeveloperSettings` (Project Settings → Game → "GoN <System>", `Config=Game, defaultconfig`) mirrored to a pure struct with `ToPure()` (pattern: `FGoNMovementMetrics::ToPure`), or JSON under `Plugins/GhostsOfNovember/Data/<System>/`. Any new `Data/<X>` folder must be staged: in the owning module's Build.cs add `RuntimeDependencies.Add("$(PluginDir)/Data/<X>/...", StagedFileType.UFS);` (NonUFS for files a web browser must load from disk: `Data/UI`, `Data/Fonts`).
- Every milestone's runtime features are switchable: a cvar `gon.<system>.enable` (default 1) checked where the system starts doing work, so one broken system doesn't block testing the others.

## Module layout (dependency order: a module may depend ONLY on modules above it)
1. `GoNCore` — settings, save, build info, JSON, logic test harness. (M3 adds `UGoNWorldClockSubsystem`: time of day / day-night.)
2. `GoNNarrative` — missions/beats, consequences, checkpoints, timeline validator. (M4 adds the dialogue graph + dialogue subsystem + bark API; M6 adds cinematic director + scene director.)
3. `GoNCharacter` — `AGoNCharacter`, movement, anim, input set, wounded comrade, traverse probe.
4. `GoNBlockout` — blockout pieces, ALL markers (`GoNMarkers.h`), gym game mode, gym layouts (pure, `Logic/GoNGymLayout*`), checkpoint/retry service.
5. `GoNStealth` — suspicion core (pure) + stealth subsystem/observer component.
6. `GoNCombat` (M5) — weapons, ballistics, loot, sabotage.
7. `GoNSurvival` (M5) — resources, fatigue, cold, wounds.
8. `GoNAI` — perception, guards, patrols, dogs, spawning from markers; M5 adds the combat layer (then depends on GoNCombat).
9. `GoNSociety` (M4) — trust, message network, civilians.
10. `GoNKnowledge` (M4) — notebook, codex.
11. `GoNAudio` (M6) — music states, procedural sounds, VO, ambience.
12. `GoNUI` (M4 subtitles/notebook UI; M6 menus, briefing web widget, title cards, failure screen).
13. `GoNGame` (NEW top module, create it the first time you need integration code) — chapter flow, gym scenario glue, level validation, perf tools, soft-lock sweep. Add it to the `.uplugin` (Type Runtime, LoadingPhase Default).

Placement is **marker-based**: gameplay actors (guards, dogs, civilians, crates, contacts) are spawned from markers in the level (`AGoNSpawnPoint` and friends), never from hard-coded positions in mission code. Gym layouts are pure C++ descriptions (boxes + markers) that the gym game mode instantiates; the spawning modules (AI, Society, Combat) find the markers at BeginPlay. This keeps lower modules free of upward dependencies and makes the user's real levels work the same way (M7).

## UE 5.7 compile-safety checklist (MANDATORY — re-read every new/changed Unreal file against it before you finish)
1. **Shadowing is an error** (C4456/C4457/C4458): no local, parameter or lambda parameter may share a name with another local in an enclosing scope or with ANY member of the class or its bases (including private engine members). Dangerous names in actors/components: `Owner`, `Tags`, `Instigator`, `RootComponent`, `Children`, `Controller`, `PlayerState`, `Mesh`, `CapsuleComponent`, `CharacterMovement`, `Velocity`, `Bounds`, `Mobility`, `Pawn`, `Blackboard`, `BrainComponent`, `PathFollowingComponent`, `PerceptionComponent`, `Canvas`, `PlayerOwner`, `Slot`, `Visibility`, `World` (when a member), `Stance`, `Probe`, … Also members of OUR classes (read the header). Use descriptive local names (`GuardMesh`, `OwnerActor`, `HitBox`).
2. Forward declarations at namespace scope only (top of header), never inside a `UCLASS` body.
3. Every cross-module pure symbol carries its module macro with a fallback at the top of the header:
   `#ifndef GONSTEALTH_API` / `#define GONSTEALTH_API` / `#endif`. Rule: put the macro on EVERY non-inline free function and EVERY struct/class with out-of-line member functions in `Public/Logic` headers (no exceptions; the standalone build cannot catch a missing export). Inline/template code needs none.
4. UHT: `#include "X.generated.h"` is the LAST include of every header with UCLASS/USTRUCT/UENUM. UPROPERTY/UFUNCTION types must be UHT types (`int32` not `int`, `float/double`, `FString`, `FName`, `FText`, `FVector`, `TArray`, `TMap`, `TSoftObjectPtr`, `TSoftClassPtr`, `TObjectPtr<>` for object pointers in headers). Never std:: types or namespaced pure types in UPROPERTY/UFUNCTION — keep pure members as plain C++ members (non-UPROPERTY). `UENUM(BlueprintType) enum class EGoNX : uint8`. BlueprintReadOnly/Write on private members needs `meta = (AllowPrivateAccess = "true")`. BlueprintCallable needs `Category`. UINTERFACE: `UINTERFACE(MinimalAPI, meta = (CannotImplementInterfaceInBlueprint))` + `class GONX_API IGoNThing { GENERATED_BODY() public: virtual ... }` (plain virtuals, not pure `= 0` if you can give a default).
5. Dynamic delegates: `DECLARE_DYNAMIC_MULTICAST_DELEGATE_*` at namespace scope before the UCLASS; `AddDynamic` handlers are `UFUNCTION()` with the exact signature. Prefer native `DECLARE_MULTICAST_DELEGATE_*` for C++-only events.
6. Includes (IWYU, no monolithic headers): e.g. `Engine/World.h`, `EngineUtils.h` (TActorIterator), `Kismet/GameplayStatics.h`, `DrawDebugHelpers.h`, `Components/*.h`, `GameFramework/*.h`, `AIController.h`, `NavigationSystem.h`, `Engine/Canvas.h`, `Debug/DebugDrawService.h`, `HAL/IConsoleManager.h`, `Engine/Engine.h`, `TimerManager.h`, `Engine/StaticMesh.h`, `UObject/ConstructorHelpers.h`, `Framework/Application/SlateApplication.h`, `Widgets/SCompoundWidget.h`, `Fonts/FontCache.h`, `Rendering/DrawElements.h`.
7. Build.cs: add every engine module you include (`AIModule`, `NavigationSystem`, `GameplayTasks`, `Slate`, `SlateCore`, `UMG`, `WebBrowser`, `LevelSequence`, `MovieScene`, `AudioMixer`, `RHI`, `Projects`, `DeveloperSettings`, `InputCore`, `EnhancedInput`, …) and every GoN module dependency. Add every engine plugin you need to the `.uplugin` `Plugins` list.
8. Only APIs you are sure exist in UE 5.x and are not deprecated-to-error in 5.7. When unsure use the simpler/older API (e.g. own line traces instead of AIPerception; `AAIController::MoveToLocation` instead of gameplay tasks; Slate `SCompoundWidget::OnPaint` + `FSlateDrawElement` instead of UMG designer assets). No editor-only APIs in runtime modules (wrap any in `#if WITH_EDITOR`).
9. Windows/UE macro clashes: never name anything `DrawText`, `GetObject`, `CreateFile`, `Yield`, `ERROR`, `DELETE`, `IN`, `OUT`, `check`, `verify`, `ensure`, `PI`, `TRUE`, `FALSE`.
10. Unity builds merge a module's .cpp files: file-local helpers go in a uniquely named namespace per file (`namespace GoNGuardControllerDetail`), never in anonymous namespaces with common names; no duplicate `static` function names; console objects have unique names.
11. `const`-correctness: don't call non-const engine functions through const pointers; `GetWorld()` from a const actor returns `UWorld*` (fine). `TActorIterator<T>(World)` needs a non-null `UWorld*`.
12. `FString::Printf(TEXT("%s"), *Str)`; float format `%.1f` with `double` OK. `FName` → `ToString()`.
13. `UPROPERTY()` every UObject pointer member you own (GC), or use `TWeakObjectPtr`. Slate widgets held in `TSharedPtr`.
14. No `auto` lambdas capturing `this` in timers without weak checks; prefer `FTimerDelegate::CreateUObject` / `CreateWeakLambda(this, ...)`.
15. A header change needs a full rebuild — list every new or changed header in CHANGELOG.

## Content rules (design doc; enforced)
- One timeline; real people's lines are sourced or tagged dramatized («حوار درامي متخيّل»); no real figure moved between regions; no reward for harming civilians or prisoners; no interactive torture; **no real explosive or weapon-making instructions anywhere** (UI, text, data, comments); French antagonists are composite and realistic, never cartoons; harkis/settlers/soldiers/civilians are not monoliths.
- Fictional fighters Salah / Ammar / Lakhdar and the douar woman **Yamina** (renamed from Zohra; id `fic_douar_woman_01`) stay placeholders `approved: false`.
- Run `bash Tools/run_logic_tests.sh --validate` — narrative data must have 0 errors.

## Assets
You cannot open `.uasset`. Use only paths in `Docs/Brief/ASSET_MANIFEST.md` (UE mannequin meshes/anims, engine content such as `/Engine/BasicShapes/Cube.Cube`, `/Engine/BasicShapes/Sphere.Sphere`, `/Engine/BasicShapes/Cylinder.Cylinder`, `/Engine/BasicShapes/Cone.Cone`, `/Engine/EngineMaterials/...`) or user-promised paths. For anything missing: expose a data slot (soft pointer in settings/data) + a placeholder fallback + a log line, and add a row to `Docs/MISSING_ASSETS.md` (exact expected path, type, what it should be, which system uses it). Dog: static mesh `/Game/Characters/Dog/SM_Dog.SM_Dog` (German shepherd, ~82 cm tall, ~110 cm long, no skeleton/material; modern vest not period-correct, to be replaced).

## Deliverables of every milestone (in the repo)
1. Code + data + pure tests (all logic tests pass in both builds; `--validate` 0 errors).
2. `CHANGELOG.md`: insert ONE new section directly below the line `Newest first. ...` (above the previous newest section), titled `## M<n> — <title> (2026-10-31)`, with: **Rebuild** note; **What's new** (short); **Files** (new / changed, paths relative to `Plugins/GhostsOfNovember/Source` or repo); **Header changes** (every new/changed `.h`, one line each with what changed); **Build.cs / .uplugin changes**; **New console commands** (table); **Verified here** (test counts) and **Not verified** (all Unreal code); **Your checks** (3–5, numbered, concrete: command → what you should see). No hash table (the coordinator adds it at the end).
3. `TEST_PLAN.md` at the repo root: append a section `## M<n> — <title>` with the step-by-step session (exact console commands, what to see, what to send back if it fails). Create the file if it does not exist (with a short intro on how to run commands and where logs are: `Saved/Logs/MyProject2.log`).
4. `Docs/MISSING_ASSETS.md`: append rows for your milestone (create with a table header if missing).
5. `README.md`: update the status line and add a short section for the systems you built (commands, how to use).
6. Final self-review: re-read every new/changed Unreal `.h` and `.cpp` once purely for compile errors against the checklist above, and fix what you find.

## Report back (your final message)
- Files created/changed (grouped).
- Logic test totals from both builds and `--validate` result.
- Design decisions the next milestone must know (public APIs, events, markers, data files, cvars).
- The 5 Unreal spots you are least sure compile (file:line + why).
- Anything you could not do and why.
